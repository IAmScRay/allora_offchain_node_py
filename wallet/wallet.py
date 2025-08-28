import logging

import os
os.environ.setdefault("TEMPORARILY_DISABLE_PROTOBUF_VERSION_CHECK", "true")

import time

import hashlib
from threading import Lock

import ecdsa
import hdwallets
import bech32
from mnemonic import Mnemonic
from Crypto.Hash.RIPEMD160 import new as ripemd160_new

from api_node.api_node import APINode
from transactions.tx import Transaction

from proto_out.emissions.v3 import nonce_pb2 as nonce
from proto_out.emissions.v9 import tx_pb2 as emissions, inputworker_pb2 as worker
from cosmospy_protobuf.cosmos.crypto.secp256k1 import keys_pb2 as keys
from google.protobuf.any_pb2 import Any


class Wallet:
    """
    A class that represents worker wallet, initialized with a seed phrase.

    When initializing, if wallet details like account number & sequence **cannot** be fetched,
    wallet is not suitable for further operations.
    """
    logger: logging.Logger = logging.getLogger(__name__)

    initialized: bool = False

    priv_key_bytes: bytes
    pub_key_bytes: bytes

    address: str
    account_number: int = -1
    sequence: int = -1
    balance: int = 0

    gas_adjustment: float

    api_node: APINode

    def __init__(
            self,
            seed_phrase: str,
            gas_adjustment: float,
            api_node: APINode
    ):
        seed_bytes = Mnemonic.to_seed(seed_phrase)
        hd_wallet = hdwallets.BIP32.from_seed(seed_bytes)

        self.priv_key_bytes = hd_wallet.get_privkey_from_path("m/44'/118'/0'/0/0")
        self.pub_key_bytes = (ecdsa.
                              SigningKey.
                              from_string(self.priv_key_bytes, curve=ecdsa.SECP256k1).
                              get_verifying_key().
                              to_string("compressed")
                              )

        pubkey_obj = keys.PubKey(key=self.pub_key_bytes)

        self.pub_key_obj = Any()
        self.pub_key_obj.Pack(pubkey_obj)
        self.pub_key_obj.type_url = "/cosmos.crypto.secp256k1.PubKey"

        s = hashlib.new("sha256", self.pub_key_bytes).digest()
        ripemd160 = ripemd160_new()
        ripemd160.update(s)
        r = ripemd160.digest()
        five_bit_r = bech32.convertbits(r, 8, 5)
        self.address = bech32.bech32_encode("allo", five_bit_r)

        self.logger.info(f"Initializing worker wallet (address: `{self.address}`)")

        self.gas_adjustment = gas_adjustment

        self.api_node = api_node
        self.api_node.fetch_wallet_details(self)

        if self.account_number == -1 or self.sequence == -1 or self.balance == 0:
            self.logger.critical("Failed to fetch wallet details")
            return

        self.initialized = True
        self.sequence_lock = Lock()

        self.logger.info("Wallet initialized successfully!")

    def get_account_number(self) -> int:
        """
        Gets an account number of this wallet.
        """
        return self.account_number

    def get_sequence(self) -> int:
        """
        Gets current sequence of this wallet.
        """
        return self.sequence

    def increment_sequence(self):
        """
        Increments wallet's sequence by **1** after transaction is executed.
        """
        self.sequence += 1

    def get_balance(self) -> int:
        """
        Gets current balance of this wallet
        """
        return self.balance

    def get_address(self) -> str:
        """
        Gets address of this wallet.
        """
        return self.address

    def get_pub_key_bytes(self) -> bytes:
        """
        Gets wallet's public key in bytes.
        """
        return self.pub_key_bytes

    def get_pub_key_obj(self) -> Any:
        """
        Gets wallet's public key as a Protobuf-encoded object.
        """
        return self.pub_key_obj

    def get_priv_key_bytes(self) -> bytes:
        """
        Gets wallet's private key in bytes.
        """
        return self.priv_key_bytes

    def is_initialized(self) -> bool:
        """
        Returns wallet's initialization status.
        :return: ``True`` if everything's in place, left as ``False`` otherwise.
        """
        return self.initialized

    def register_for_topic(self, topic_id: int) -> bool:
        """
        Constructs and submits a ``RegisterRequest`` transaction for a specified topic.

        :param topic_id: ID of a topic that wallet is trying to register for.
        :return: ``True`` if registration is successful, ``False`` if otherwise.
        """
        with self.sequence_lock:
            self.logger.info(f"Registering wallet for topic {topic_id}...")

            self.logger.debug(f"Preparing `RegisterRequest` transaction for topic {topic_id}...")

            request = emissions.RegisterRequest(
                sender=self.address,
                topic_id=topic_id,
                owner=self.address,
                is_reputer=False
            )
            request_type = "/emissions.v9.RegisterRequest"
            timeout_height = self.api_node.get_latest_height() + 50

            tx = Transaction(self)
            tx.set_tx_body(
                request_type=request_type,
                request=request,
                timeout_height=timeout_height
            )

            self.logger.debug("Estimating gas for `RequestRequest` transaction...")
            retries = 3
            gas_limit = -1
            while retries > 0 and gas_limit == -1:
                gas_limit = self.api_node.simulate_tx(tx.get_tx_bytes())

                if gas_limit == -1:
                    log_message = f"Could not estimate gas limit, retrying..."
                    if retries > 1 or retries == 0:
                        log_message += f" ({retries} retries left)"
                    else:
                        log_message += f" ({retries} retry left)"

                    self.logger.warning(log_message)

                    retries -= 1
                    time.sleep(1)

            if gas_limit == -1:
                self.logger.warning(f"Failed to broadcast `RegisterRequest` transaction for topic {topic_id}: "
                                    f"cannot estimate gas limit")
                return False

            tx.set_fee(
                gas_limit=gas_limit,
                gas_price=self.api_node.get_gas_price(),
                gas_adjustment=self.gas_adjustment
            )

            self.logger.debug(f"Estimated fee: {tx.get_fee()} uALLO")

            if tx.get_fee() > self.balance:
                self.logger.warning(f"Not enough balance to register for topic {topic_id}: "
                                    f"required fee – {tx.get_fee()} uALLO, balance – {self.get_balance()} uALLO")
                return False

            retries = 5
            tx_hash = ""
            while retries > 0 and tx_hash == "":
                tx_hash = self.api_node.broadcast_tx(tx.get_tx_bytes())

                if tx_hash == -1:
                    log_message = f"Could not broadcast transaction, retrying..."
                    if retries > 1 or retries == 0:
                        log_message += f" ({retries} retries left)"
                    else:
                        log_message += f" ({retries} retry left)"

                    self.logger.warning(log_message)

                    retries -= 1
                    time.sleep(3)

            if tx_hash == -1:
                self.logger.critical(f"Failed to register for topic {topic_id}: transaction cannot be broadcasted")
                return False

            self.logger.info(f"Transaction broadcasted, hash: {tx_hash}")

            message = self.api_node.wait_for_tx(tx_hash)
            if message != "":
                self.logger.critical(f"Failed to execute transaction {tx_hash}: {message}")

                self.balance -= tx.get_fee()
                self.increment_sequence()
                return False

            self.logger.info(f"Registered wallet successfully! (topic {topic_id})")

            self.balance -= tx.get_fee()
            self.increment_sequence()
            return True

    def submit_inference(
            self,
            inference_value: float,
            topic_id: int,
            inference_nonce: int
    ) -> bool:
        """
        Constructs and submits a ``InsertWorkerPayloadRequest`` transaction for a specified topic
        using provided inference value and inference (block height) nonce.

        When transaction is executed (either successfully or not), ``sequence`` is incremented to avoid
        re-fetching wallet details from API node.

        :param inference_value: fetched inference value
        :param topic_id: ID of a topic that worker is trying to submit an inference for.
        :param inference_nonce: topic-specific inference (block height) nonce.
        """
        with self.sequence_lock:
            self.logger.info(f"Submitting inference value `{inference_value}` for topic {topic_id}...")

            self.logger.debug(f"Preparing `InsertWorkerPayloadRequest` transaction for topic {topic_id}...")

            inference_bundle = worker.InputInferenceForecastBundle(
                inference=worker.InputInference(
                    topic_id=topic_id,
                    block_height=inference_nonce,
                    inferer=self.address,
                    value=str(inference_value),
                    extra_data=b"",
                    proof=""
                ),
                forecast=None
            )

            payload_bytes = inference_bundle.SerializeToString()

            signature = ecdsa.SigningKey.from_string(self.priv_key_bytes, curve=ecdsa.SECP256k1).sign_deterministic(
                payload_bytes,
                hashfunc=hashlib.sha256,
                sigencode=ecdsa.util.sigencode_string_canonize
            )

            worker_data_bundle = worker.InputWorkerDataBundle(
                worker=self.address,
                nonce=nonce.Nonce(block_height=inference_nonce),
                topic_id=topic_id,
                inference_forecasts_bundle=inference_bundle,
                inferences_forecasts_bundle_signature=signature,
                pubkey=self.pub_key_bytes.hex()
            )

            request = emissions.InsertWorkerPayloadRequest(
                sender=self.address,
                worker_data_bundle=worker_data_bundle
            )
            request_type = "/emissions.v9.InsertWorkerPayloadRequest"
            timeout_height = self.api_node.get_latest_height() + 50

            tx = Transaction(self)
            tx.set_tx_body(
                request_type=request_type,
                request=request,
                timeout_height=timeout_height
            )

            self.logger.debug("Estimating gas for `InsertWorkerPayloadRequest` transaction...")
            retries = 3
            gas_limit = -1
            while retries > 0 and gas_limit == -1:
                gas_limit = self.api_node.simulate_tx(tx.get_tx_bytes())

                if gas_limit == -1:
                    log_message = f"Could not estimate gas limit, retrying..."
                    if retries > 1 or retries == 0:
                        log_message += f" ({retries} retries left)"
                    else:
                        log_message += f" ({retries} retry left)"

                    self.logger.warning(log_message)

                    retries -= 1
                    time.sleep(1)

            if gas_limit == -1:
                self.logger.warning(f"Failed to broadcast `InsertWorkerPayloadRequest` transaction "
                                    f"for topic {topic_id}: cannot estimate gas limit")
                return True

            tx.set_fee(
                gas_limit=gas_limit,
                gas_price=self.api_node.get_gas_price(),
                gas_adjustment=self.gas_adjustment
            )

            self.logger.debug(f"Estimated fee: {tx.get_fee()} uALLO")

            if tx.get_fee() > self.balance:
                self.logger.warning(f"Not enough balance to submit inference for topic {topic_id}: "
                                    f"required fee – {tx.get_fee()} uALLO, balance – {self.get_balance()} uALLO")
                return False

            retries = 5
            tx_hash = ""
            while retries > 0 and tx_hash == "":
                tx_hash = self.api_node.broadcast_tx(tx.get_tx_bytes())

                if tx_hash == -1:
                    log_message = f"Could not broadcast transaction, retrying..."
                    if retries > 1 or retries == 0:
                        log_message += f" ({retries} retries left)"
                    else:
                        log_message += f" ({retries} retry left)"

                    self.logger.warning(log_message)

                    retries -= 1
                    time.sleep(3)

            if tx_hash == -1:
                self.logger.warning(f"Failed to submit inference for topic {topic_id}: transaction cannot be broadcasted")
                return True

            self.logger.info(f"Transaction broadcasted, hash: {tx_hash}")

            message = self.api_node.wait_for_tx(tx_hash)
            if message != "":
                self.logger.critical(f"Failed to execute transaction {tx_hash}: {message}")
            else:
                self.logger.info(f"Inference submitted successfully! (topic {topic_id})")

            self.balance -= tx.get_fee()
            self.increment_sequence()

            return True
