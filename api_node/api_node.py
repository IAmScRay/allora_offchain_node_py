import time
from json import JSONDecodeError

import httpx

from params.api_node_params import APINodeParams

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from wallet.wallet import Wallet


class APINode:
    """
    A class that represents an API (LCD) blockchain node.
    """
    params: APINodeParams

    chain_id: str = ""
    gas_price: float = 0.0

    client: httpx.Client
    connected: bool = False

    def __init__(
            self,
            params: APINodeParams,
            is_wallet_node: bool = False
    ):
        self.params = params

        self.connected = self.create_client(is_wallet_node)
        if not self.connected:
            self.client.close()

    def get_chain_id(self) -> str:
        """
        Gets a network's chain ID of the network node is running for.
        """
        return self.chain_id

    def fetch_chain_id(self):
        """
        Fetches & updates network's chain ID.
        """
        self.params.get_logger().debug("Fetching node details...")

        try:
            req = self.client.get(
                url="/cosmos/base/tendermint/v1beta1/node_info"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot fetch node details ({e})")
            return

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch chain ID: {req.status_code} HTTP response code")
            return

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract chain ID")
            return

        if "default_node_info" not in resp:
            self.params.get_logger().critical("Failed to fetch chain ID: `default_node_info` field is not present")
            return

        self.chain_id = resp["default_node_info"]["network"]
        self.params.get_logger().debug(f"Received chain ID `{self.get_chain_id()}`")

    def get_gas_price(self) -> float:
        """
        Gets price per unit of gas.
        """
        return self.gas_price

    def update_gas_price(self):
        """
        Fetches & updates price per unit of gas
        """
        self.params.get_logger().debug("Fetching gas price...")

        try:
            req = self.client.get(
                url="/feemarket/v1/gas_price/uallo"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot fetch gas price (`{e}`)")
            return

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch gas price: {req.status_code} HTTP response code")
            return

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract gas price")
            return

        if "price" not in resp:
            self.params.get_logger().critical("Failed to fetch gas price: `minimum_gas_price` field is not present")
            return

        self.gas_price = float(resp["price"]["amount"])
        self.params.get_logger().debug(f"Received gas price: {self.get_gas_price()} uALLO")

    def get_latest_height(self) -> int:
        """
        Fetches the latest block height.

        :return: block height as a proper ``int``, or ``-1`` if an error occurred.
        """
        self.params.get_logger().debug("Fetching latest block height...")
        try:
            req = self.client.get(
                url="/cosmos/base/tendermint/v1beta1/blocks/latest"
            )
        except httpx.RequestError:
            self.params.get_logger().critical("httpx.RequestError: cannot fetch block height")
            return -1

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch block height: {req.status_code} HTTP response code")
            return -1

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract block height")
            return -1

        if "block" not in resp:
            self.params.get_logger().critical("Failed to fetch block height: `block` field is not present")
            return -1

        self.params.get_logger().debug(f"Latest block height: {resp['block']['header']['height']}")
        return int(resp["block"]["header"]["height"])

    def create_client(self, is_wallet_node: bool) -> bool:
        """
        Creates ``httpx.Client`` object that is used for communication with a blockchain node.

        If everything goes well, ``self.client`` is a proper client object, otherwise
        further operations are not possible.
        """
        self.params.get_logger().debug("Creating `httpx.Client` object...")
        self.client = httpx.Client(
            base_url=self.params.get_api_url(),
            timeout=15.0
        )

        if is_wallet_node:
            self.fetch_chain_id()
            if self.chain_id == "":
                self.params.get_logger().critical("Failed to fetch chain ID from wallet's API node – execution aborted")
                return False

            self.update_gas_price()
            if self.gas_price == 0.0:
                self.params.get_logger().critical("Failed to fetch gas price from wallet's API node – execution aborted")
                return False
        else:
            self.params.get_logger().debug("API node is not dedicated to a wallet – no need to fetch chain ID or gas price!")

        self.params.get_logger().debug(f"Checking node's syncing status...")
        try:
            req = self.client.get(
                url="/cosmos/base/tendermint/v1beta1/syncing"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot check node's syncing status ({e})")
            return False

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to check if node is syncing: {req.status_code} HTTP response code")
            return False

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot check if node is syncing")
            return False

        if "syncing" not in resp or resp["syncing"]:
            self.params.get_logger().critical("Node is not ready: `syncing` status is `true`")
            return False

        self.params.get_logger().debug("Node is not syncing - that's good")

        self.params.get_logger().debug("Node client is ready!")
        return True

    def is_connected(self) -> bool:
        """
        Returns API node connection status.

        :return: ``True`` if connection is successful, left as ``False`` otherwise.
        """
        return self.connected

    def fetch_wallet_details(
            self,
            wallet: "Wallet"
    ):
        """
        Fetches and updates wallet's details (sequence, account number & balance).

        :param wallet: ``Wallet`` object
        """
        self.params.get_logger().debug("Fetching wallet details...")

        try:
            req = self.client.get(
                url=f"/cosmos/auth/v1beta1/account_info/{wallet.get_address()}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot fetch wallet details ({e})")
            return

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch wallet details: {req.status_code} HTTP response code")
            return

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract wallet details")
            return

        if "code" in resp or "info" not in resp or resp["info"] is None:
            if resp["code"] == 5:
                self.params.get_logger().critical(f"No details are available for wallet "
                                                  f"`{wallet.get_address()}`: is wallet funded?")
            else:
                self.params.get_logger().critical(f"Failed to fetch wallet details: {resp['message']}")

            return

        wallet.account_number = int(resp["info"]["account_number"])
        wallet.sequence = int(resp["info"]["sequence"])

        try:
            req = self.client.get(
                url=f"/cosmos/bank/v1beta1/balances/{wallet.get_address()}/by_denom",
                params={
                    "denom": "uallo"
                }
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot fetch wallet balance ({e})")
            return

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch wallet balance: {req.status_code} HTTP response code")
            return

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract wallet balance")
            return

        if "code" in resp:
            self.params.get_logger().critical(f"Failed to fetch wallet balance: {resp['message']}")
            return

        if "balance" not in resp:
            self.params.get_logger().critical(f"Failed to fetch wallet balance: `balance` field is not present")
            return

        wallet.balance = int(resp["balance"]["amount"])

        self.params.get_logger().debug(f"Wallet details fetched successfully! (account number: `{wallet.get_account_number()}`, "
                          f"sequence: `{wallet.get_sequence()}`, balance: `{wallet.get_balance()}` uALLO)")

    def simulate_tx(
            self,
            tx_bytes: str
    ) -> int:
        """
        Simulates the given transaction and returns an estimated gas limit.

        :param tx_bytes: Base64-encoded transaction bytes
        :return: gas limit as a proper ``int``, or **-1** if an error occurred
        """
        self.params.get_logger().debug("Simulating transaction for gas estimation...")

        try:
            req = self.client.post(
                url="/cosmos/tx/v1beta1/simulate",
                json={
                    "tx_bytes": tx_bytes
                }
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot estimate gas for transaction ({e})")
            return -1

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().critical("JSONDecodeError: cannot extract simulate result")
            return -1

        if "code" in resp:
            if "insufficient funds" in resp["message"]:
                self.params.get_logger().critical("Failed to simulate transaction: not enough balance")
            else:
                self.params.get_logger().critical(f"Failed to simulate transaction: `{resp['message']}`")

            return -1

        if "gas_info" not in resp:
            self.params.get_logger().critical("Failed to simulate transaction: `gas_info` field is not present")
            return -1

        self.params.get_logger().debug(f"Estimated gas limit: {resp['gas_info']['gas_used']}")
        return int(resp["gas_info"]["gas_used"])

    def broadcast_tx(
            self,
            tx_bytes: str
    ) -> str:
        """
        Broadcasts the given transaction to the network.

        :param tx_bytes: Base64-encoded transaction bytes
        :return: transaction hash if broadcast is successful, or empty string if otherwise
        """
        self.params.get_logger().debug("Broadcasting transaction...")

        try:
            req = self.client.post(
                url="/cosmos/tx/v1beta1/txs",
                json={
                    "tx_bytes": tx_bytes,
                    "mode": "BROADCAST_MODE_SYNC"
                }
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot broadcast a transaction ({e})")
            return ""

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning("JSONDecodeError: cannot extract broadcast response")
            return ""

        if "tx_response" not in resp:
            self.params.get_logger().critical("Failed to broadcast transaction: `tx_response` field is not present")
            return ""

        resp = resp["tx_response"]

        if resp["code"] != 0:
            self.params.get_logger().warning(f"Failed to broadcast transaction: {resp['raw_log']}")
            return ""

        self.params.get_logger().debug(f"Broadcasted transaction hash: {resp['txhash']}")
        return resp["txhash"]

    def wait_for_tx(
            self,
            tx_hash: str
    ) -> str:
        """
        Waits until transaction is included in a block.

        :param tx_hash: broadcasted transaction hash
        :return: empty string if no error during execution / waiting occurred, or an error message otherwise
        """
        self.params.get_logger().debug(f"Waiting for transaction to be included in a block (hash: {tx_hash})...")

        retries = self.params.get_tx_check_retries()
        receipt = None
        while retries > 0 and receipt is None:

            try:
                req = self.client.get(
                    url=f"/cosmos/tx/v1beta1/txs/{tx_hash}"
                )
            except httpx.RequestError as e:
                self.params.get_logger().critical("httpx.RequestError: cannot check if transaction is included "
                                     f"in a block ({e})")
                return "httpx.RequestError"

            try:
                resp = req.json()
            except JSONDecodeError:
                self.params.get_logger().critical("JSONDecodeError: cannot extract transaction receipt")
                break

            if "tx_response" in resp:
                receipt = resp["tx_response"]
            else:
                if "code" in resp and resp["code"] == 5:
                    time.sleep(self.params.get_tx_check_freq())
                    retries -= 1

        if receipt is None:
            return "transaction not included in a block"
        else:
            self.params.get_logger().debug(f"Transaction's block height: {receipt['height']}")
            return "" if receipt["code"] == 0 else receipt["raw_log"]

    def is_registered_for(
            self,
            wallet: "Wallet",
            topic_id: int
    ) -> bool:
        """
        Checks if worker wallet is registerted for a specified topic.

        :param wallet: ``Wallet`` object
        :param topic_id: ID of a topic that worker is trying to fetch status for
        :return: ``True`` if wallet is already registered, ``False`` if otherwise or if an error occurred
        """
        self.params.get_logger().debug(f"Checking if worker {wallet.get_address()} is registered for topic {topic_id}...")

        try:
            req = self.client.get(
                url=f"/emissions/v9/worker_registered/{topic_id}/{wallet.get_address()}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical("httpx.RequestError: cannot check if worker is registered for "
                                 f"topic {topic_id} ({e})")
            return False

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning("JSONDecodeError: cannot extract registration status")
            return False

        if "is_registered" not in resp:
            self.params.get_logger().critical(f"Failed to check registration status for topic {topic_id}: "
                                 f"`is_registered` field is not present")
            return False

        self.params.get_logger().debug(f"Registration status for topic {topic_id}: {resp['is_registered']}")
        return resp["is_registered"]

    def get_topic_nonce(
            self,
            topic_id: int
    ) -> int:
        """
        Fetches unfulfilled worker (block height) nonce for a specified topic.

        :param topic_id: ID of a topic
        :return: block height as a proper ``int``, **0** if nonce is not available yet or if an error occurred
        """
        self.params.get_logger().debug(f"Fetching worker nonce for topic {topic_id}...")

        try:
            req = self.client.get(
                url=f"/emissions/v9/unfulfilled_worker_nonces/{topic_id}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot fetch worker nonce for topic {topic_id} ({e})")
            return 0

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning("JSONDecodeError: cannot extract worker nonce")
            return 0

        if "nonces" not in resp:
            self.params.get_logger().critical(f"Failed to fetch worker nonce for topic {topic_id}: "
                                 f"`nonces` field is not present")
            return 0

        if len(resp["nonces"]["nonces"]) > 0:
            self.params.get_logger().debug(f"Worker nonce for topic {topic_id}: {resp['nonces']['nonces'][0]['block_height']}")
            return int(resp["nonces"]["nonces"][0]["block_height"])

        self.params.get_logger().debug("Nonce is not available: wait to the unfulfilled worker nonce")
        return 0

    def is_topic_active(
            self,
            topic_id: int
    ) -> bool:
        """
        Checks if topic is active onchain.

        :param topic_id: ID of a topic
        :return: ``True`` if topic is active, ``False`` if otherwise or if an error occurred
        """
        self.params.get_logger().debug(f"Checking if topic {topic_id} is active...")

        try:
            req = self.client.get(
                url=f"/emissions/v9/is_topic_active/{topic_id}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot check if topic {topic_id} is active ({e})")
            return False

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning(f"JSONDecodeError: cannot check if topic {topic_id} is active")
            return False

        if "is_active" not in resp:
            self.params.get_logger().critical(f"Failed to check if topic {topic_id} is active: "
                                 "`is_active` field is not present")
            return False

        self.params.get_logger().debug(f"Received topic active status: {resp['is_active']}")
        return resp["is_active"]

    def is_whitelisted_for(
            self,
            wallet: "Wallet",
            topic_id: int
    ) -> bool:
        """
        Checks if worker wallet is whitelisted to participate in a specified topic.

        :param wallet: ``Wallet`` object
        :param topic_id: ID of a topic that worker is trying to check whitelist status for
        :return: ``True`` if worker is whitelisted, ``False`` if otherwise or if an error occurred
        """
        self.params.get_logger().debug(f"Checking if wallet {wallet.get_address()} is whitelisted for topic {topic_id}...")

        try:
            req = self.client.get(
                url=f"/emissions/v9/is_whitelisted_topic_worker/{topic_id}/{wallet.get_address()}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(f"httpx.RequestError: cannot check if wallet is whitelisted for topic {topic_id}: ({e})")
            return False

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning("JSONDecodeError: cannot extract whitelist status")
            return False

        if "is_whitelisted_topic_worker" not in resp:
            self.params.get_logger().critical("Failed to check if wallet is whitelisted: "
                                 "`is_whitelisted_topic_worker` field is not present")
            return False

        self.params.get_logger().debug(f"Received whitelist status: {resp['is_whitelisted_topic_worker']}")
        return resp["is_whitelisted_topic_worker"]

    def is_topic_whitelisted(
            self,
            topic_id: int
    ) -> bool:
        """
        Checks if specified topic's whitelist is enabled.

        :param topic_id: ID of a topic
        :return: ``True`` if topic is whitelisted, ``False`` if otherwise or if an error occurred
        """
        self.params.get_logger().debug(f"Checking if topic {topic_id} whitelist is enabled...")

        try:
            req = self.client.get(
                url=f"/emissions/v9/is_topic_worker_whitelist_enabled/{topic_id}"
            )
        except httpx.RequestError as e:
            self.params.get_logger().critical(
                f"httpx.RequestError: cannot check if topic {topic_id} whitelist is enabled: ({e})")
            return False

        try:
            resp = req.json()
        except JSONDecodeError:
            self.params.get_logger().warning("JSONDecodeError: cannot extract topic whitelist status")
            return False

        if "is_topic_worker_whitelist_enabled" not in resp:
            self.params.get_logger().critical("Failed to check if topic whitelist is enabled: "
                                 "`is_topic_worker_whitelist_enabled` field is not present")
            return False

        self.params.get_logger().debug(f"Received topic whitelist status: {resp['is_topic_worker_whitelist_enabled']}")
        return resp["is_topic_worker_whitelist_enabled"]
