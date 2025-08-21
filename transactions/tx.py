import base64
import ecdsa
import hashlib

from cosmospy_protobuf.cosmos.base.v1beta1 import coin_pb2 as coin_proto
from cosmospy_protobuf.cosmos.tx.signing.v1beta1 import signing_pb2 as signing_proto
from cosmospy_protobuf.cosmos.tx.v1beta1 import tx_pb2 as tx_proto
from google.protobuf.any_pb2 import Any

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from wallet.wallet import Wallet


class Transaction:
    """
    A class that represents a transaction.

    Each transaction is initialized with a ``SignerInfo`` and
    ``Fee`` objects right away. Transaction fee can be updated after gas estimation
    using ``set_fee()`` method.

    App-specific messages are set using ``set_tx_body()`` method.
    """
    wallet: "Wallet"

    fee: tx_proto.Fee
    signer_info: tx_proto.SignerInfo

    tx_body: tx_proto.TxBody

    def __init__(
            self,
            wallet: "Wallet"
    ):
        self.wallet = wallet

        self.fee = tx_proto.Fee(
            gas_limit=0,
            amount=[coin_proto.Coin(denom="uallo", amount=str(0))]
        )

        self.signer_info = tx_proto.SignerInfo(
            public_key=self.wallet.get_pub_key_obj(),
            mode_info=tx_proto.ModeInfo(
                single=tx_proto.ModeInfo.Single(mode=signing_proto.SIGN_MODE_DIRECT)
            ),
            sequence=wallet.get_sequence()
        )

    def set_tx_body(
            self,
            request_type: str,
            request,
            timeout_height: int
    ):
        """
        Adds a message to the transaction's body.

        :param request_type: full transaction path (e.g. ``/emissions.v9.InsertWorkerPayloadRequest``)
        :param request: constructed message
        :param timeout_height: block height at which transaction is considered invalid
        """

        msg_any = Any()
        msg_any.Pack(request)
        msg_any.type_url = request_type

        self.tx_body = tx_proto.TxBody(
            messages=[msg_any],
            memo="",
            timeout_height=timeout_height
        )

    def set_fee(
            self,
            gas_limit: int,
            gas_price: float
    ):
        """
        Sets a gas fee with an adjustment to the gas limit.

        :param gas_limit: estimated gas limit
        :param gas_price: price per unit of gas
        """
        self.fee = tx_proto.Fee(
            gas_limit=int(gas_limit * 1.5),
            amount=[coin_proto.Coin(denom="uallo", amount=str(int(gas_limit * 1.5 * gas_price)))]
        )

    def get_tx_bytes(self) -> str:
        """
        Constructs a signed Base64-encoded transaction that is ready to be simulated
        (when estimating gas limit), or broadcasted to the network.
        :return: Base64-encoded transaction bytes
        """
        auth_info = tx_proto.AuthInfo(
            signer_infos=[self.signer_info],
            fee=self.fee
        )

        sign_doc = tx_proto.SignDoc(
            body_bytes=self.tx_body.SerializeToString(),
            auth_info_bytes=auth_info.SerializeToString(),
            chain_id=self.wallet.api_node.get_chain_id(),
            account_number=self.wallet.get_account_number()
        )

        sign_bytes = sign_doc.SerializeToString()
        final_sig = ecdsa.SigningKey.from_string(self.wallet.get_priv_key_bytes(), curve=ecdsa.SECP256k1).sign_deterministic(
            sign_bytes,
            hashfunc=hashlib.sha256,
            sigencode=ecdsa.util.sigencode_string_canonize
        )

        tx_raw = tx_proto.TxRaw(
            body_bytes=self.tx_body.SerializeToString(),
            auth_info_bytes=auth_info.SerializeToString(),
            signatures=[final_sig]
        )

        tx_bytes = tx_raw.SerializeToString()
        tx_base64 = base64.b64encode(tx_bytes).decode()

        return tx_base64
