import logging


class WorkerParams:
    """
    A class that represents worker parameters.

    There are default values for non-critical parameters if they are not present
    in worker's configuration dictionary.
    """
    logger: logging.Logger

    topic_id: int
    inference_url: str

    nonce_fetch_freq: int = 5

    inference_fetch_retries: int = 5
    inference_fetch_retry_freq: int = 3

    def __init__(
            self,
            logger: logging.Logger,
            params: dict
    ):
        self.logger = logger

        self.topic_id = params["topic_id"]
        self.inference_url = params["inference_url"]

        if "nonce_fetch_freq" not in params or params["nonce_fetch_freq"] <= 0:
            self.logger.warning(f"`nonce_fetch_freq` field is not present or ≤ `0` for topic {self.topic_id}: "
                                f"a default parameters of `{self.nonce_fetch_freq}` will be used")
        else:
            self.nonce_fetch_freq = params["nonce_fetch_freq"]

        if "inference_fetch_retries" not in params or params["inference_fetch_retries"] <= 0:
            self.logger.warning(f"`inference_fetch_retries` field is not present or ≤ `0` for topic {self.topic_id}: "
                                f"a default parameters of `{self.inference_fetch_retries}` will be used")
        else:
            self.inference_fetch_retries = params["inference_fetch_retries"]

        if "inference_fetch_retry_freq" not in params or params["inference_fetch_retry_freq"] <= 0:
            self.logger.warning(f"`inference_fetch_retry_freq` field is not present or ≤ `0` for topic {self.topic_id}: "
                                f"a default parameters of `{self.inference_fetch_retry_freq}` will be used")
        else:
            self.inference_fetch_retry_freq = params["inference_fetch_retry_freq"]

    def get_logger(self) -> logging.Logger:
        """
        Gets a ``Logger`` object for this worker.
        :return:
        """
        return self.logger

    def get_topic_id(self) -> int:
        """
        Gets a topic ID worker is running for.
        """
        return self.topic_id

    def get_inference_url(self) -> str:
        """
        Gets a URL of an inference endpoint for this worker
        to fetch inferences from.
        """
        return self.inference_url

    def get_nonce_fetch_freq(self) -> int:
        """
        Gets frequency (in seconds) of worker checking
        unfulfilled worker nonce.
        """
        return self.nonce_fetch_freq

    def get_inference_fetch_retries(self) -> int:
        """
        Gets number of retries when worker is fetching
        an inference from inference endpoint & fails to do so.
        """
        return self.inference_fetch_retries

    def get_inference_fetch_retry_freq(self) -> int:
        """
        Gets frequency (in seconds) of worker retries
        when it fails to fetch an inference from inference endpoint.
        """
        return self.inference_fetch_retry_freq
