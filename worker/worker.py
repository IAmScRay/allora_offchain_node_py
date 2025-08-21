import time
from threading import Event, Thread

import httpx

from api_node.api_node import APINode
from params.worker_params import WorkerParams

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from wallet.wallet import Wallet


class Worker(Thread):
    """
    A class that represents a worker for a specific topic.

    This class handles inference value fetching and invoking ``Wallet``'s
    transaction submission logic.
    """
    params: WorkerParams

    wallet: "Wallet"
    api_node: APINode

    inference_client: httpx.Client

    latest_used_nonce: int

    def __init__(
            self,
            wallet: "Wallet",
            api_node: APINode,
            worker_params: WorkerParams
    ):
        self.params = worker_params

        super().__init__(name=f"Worker (topic {self.params.get_topic_id()})")

        self.wallet = wallet
        self.api_node = api_node

        self.inference_client = httpx.Client(timeout=15.0)

        self.latest_used_nonce = 0

        self.stop_event = Event()

    def fetch_inference(self) -> float | None:
        """
        Fetches an inference value from inference endpoint.

        :return: predicted value as ``float``, or ``None`` if endpoint is unavailable
        """
        self.params.get_logger().debug(f"Fetching inference value from endpoint `{self.inference_client.base_url}`...")

        try:
            req = self.inference_client.get(url=self.params.get_inference_url())
        except httpx.RequestError:
            return None

        if req.status_code in (403, 429, 500, 503):
            self.params.get_logger().critical(f"Failed to fetch inference for topic {self.params.get_topic_id()}: "
                                 f"{req.status_code} HTTP response code")
            return None

        self.params.get_logger().debug(f"Received inference value: {req.text}")
        return float(req.text)


    def run(self):
        """
        Whole worker magic is here.

        This method runs checks on the API node, then checks topic-related conditions,
        and if everything goes well - well, worker starts working! 💪
        """
        if not self.api_node.is_connected():
            self.params.get_logger().critical("API node client is not connected – execution aborted")
            return

        if not self.api_node.is_topic_active(self.params.get_topic_id()):
            self.params.get_logger().warning(f"Topic {self.params.get_topic_id()} is not active - execution aborted")
            return

        if self.api_node.is_topic_whitelisted(self.params.get_topic_id()):
            if not self.api_node.is_whitelisted_for(self.wallet, self.params.get_topic_id()):
                self.params.get_logger().warning(f"Worker wallet is not whitelisted "
                                                 f"for topic {self.params.get_topic_id()} – execution aborted")
                return

        if not self.api_node.is_registered_for(self.wallet, self.params.get_topic_id()):
            proceed = self.wallet.register_for_topic(self.params.get_topic_id())

            if not proceed:
                self.params.get_logger().critical(f"Worker cannot be registered "
                                                  f"for topic {self.params.get_topic_id()} - execution aborted")
                return

        if not self.api_node.is_topic_active(self.params.get_topic_id()):
            self.params.get_logger().warning(f"Topic {self.params.get_topic_id()} is not active - execution aborted")
            return

        self.params.get_logger().info(f"Started worker thread for topic {self.params.get_topic_id()}")

        try:
            while not self.stop_event.is_set():
                proceed = self.api_node.is_topic_active(self.params.get_topic_id())
                if not proceed:
                    self.params.get_logger().warning(f"Topic {self.params.get_topic_id()} is not active anymore, "
                                        f"aborting further execution...")
                    self.stop()
                    continue

                inference_nonce = self.api_node.get_topic_nonce(self.params.get_topic_id())
                if inference_nonce > 0 and inference_nonce > self.latest_used_nonce:
                    self.params.get_logger().info(f"Found new worker nonce, requesting inference "
                                                  f"for topic {self.params.get_topic_id()}...")

                    retries = self.params.get_inference_fetch_retries()
                    inference_value = None
                    while retries > 0 and inference_value is None:
                        inference_value = self.fetch_inference()

                        if inference_value is None:
                            log_message = f"Could not fetch inference, retrying..."
                            if retries > 1 or retries == 0:
                                log_message += f" ({retries} retries left)"
                            else:
                                log_message += f" ({retries} retry left)"

                            self.params.get_logger().warning(log_message)

                            retries -= 1
                            time.sleep(self.params.get_inference_fetch_retry_freq())

                    if inference_value is None:
                        self.params.get_logger().warning(f"Failed to fetch inference value "
                                                         f"for topic {self.params.get_topic_id()}: "
                                                         f"maybe check if inference endpoint is available?...")
                    else:
                        self.params.get_logger().info(f"Inference value for "
                                                      f"topic {self.params.get_topic_id()}: {inference_value}")

                        self.wallet.submit_inference(
                            inference_value=inference_value,
                            topic_id=self.params.get_topic_id(),
                            inference_nonce=inference_nonce
                        )

                        self.latest_used_nonce = inference_nonce
                else:
                    self.params.get_logger().debug(f"Latest used nonce: {self.latest_used_nonce}, "
                                                   f"inference (block height) nonce: {inference_nonce}")
                    self.params.get_logger().info("No new worker nonce found")

                time.sleep(self.params.get_nonce_fetch_freq())
        except Exception as e:
            self.params.get_logger().critical(f"Error occurred: {e}")
        finally:
            self.inference_client.close()
            self.params.get_logger().info("Worker thread stopped")

    def stop(self):
        """
        Sets the ``stop_event`` so the thread can exit graciously.
        """
        self.stop_event.set()
