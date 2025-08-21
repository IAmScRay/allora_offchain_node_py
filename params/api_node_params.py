import logging


class APINodeParams:
    """
    A class that represents API node parameters.

    There are default values for non-critical parameters
    """
    logger: logging.Logger

    api_url: str

    tx_check_retries: int = 10
    tx_check_freq: int = 3

    def __init__(
            self,
            logger: logging.Logger,
            params: dict
    ):
        self.logger = logger

        self.api_url = params["api_url"]

        if "tx_check_retries" not in params or params["tx_check_retries"] <= 0:
            self.logger.warning(f"`tx_check_retries` field is not present for API node or ≤ `0`: "
                                f"a default parameters of `{self.tx_check_retries}` will be used")
        else:
            self.tx_check_retries = params["tx_check_retries"]

        if "tx_check_freq" not in params or params["tx_check_freq"] <= 0:
            self.logger.warning(f"`tx_check_freq` field is not present for API node or ≤ `0`: "
                                f"a default parameters of `{self.tx_check_freq}` will be used")
        else:
            self.tx_check_freq = params["tx_check_freq"]

    def get_logger(self) -> logging.Logger:
        """
        Gets a ``Logger`` object for this API node.
        :return:
        """
        return self.logger

    def get_api_url(self) -> str:
        """
        Gets an API URL of a blockchain node.
        """
        return self.api_url

    def get_tx_check_retries(self) -> int:
        """
        Gets number of retries when API node is checking
        if transaction is included in a block.
        """
        return self.tx_check_retries

    def get_tx_check_freq(self) -> int:
        """
        Gets frequency (in seconds) of API node retries
        when it checks if transaction is included in a block.
        """
        return self.tx_check_freq
