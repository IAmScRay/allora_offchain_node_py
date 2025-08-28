import json
import logging
import os
import time
from json import JSONDecodeError

from api_node.api_node import APINode
from params.api_node_params import APINodeParams

from worker.worker import Worker
from params.worker_params import WorkerParams

from wallet.wallet import Wallet

RESET = "\x1b[0m"
COLOR_MAP = {
    "DEBUG": "\x1b[33m",         # Yellow
    "INFO": "\x1b[32m",          # Green
    "WARNING": "\x1b[38;5;208m", # Orange
    "ERROR": "\x1b[31m",         # Red
    "CRITICAL": "\x1b[41m",      # Red BG
}


class ColoredFormatter(logging.Formatter):
    """
    Custom color ``Formatter`` class for ``logging.Logger`` to use.
    """
    def format(self, record):
        levelname = record.levelname
        if levelname in COLOR_MAP:
            record.colored_levelname = f"{COLOR_MAP[levelname]}[{levelname}]{RESET}"
        else:
            record.colored_levelname = f"[{levelname}]"
        return super().format(record)


def setup_logger(debug: bool = False):
    """
    Sets up terminal & file logging.

    :param debug: enable/disable debugging logs
    """
    log_format_console = "%(asctime)s [%(threadName)s] %(colored_levelname)s %(message)s"
    log_format_file = "%(asctime)s [%(threadName)s] [%(levelname)s] %(message)s"

    console_formatter = ColoredFormatter(fmt=log_format_console, datefmt="%d.%m.%Y %H:%M:%S")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    os.makedirs("logs", exist_ok=True)

    file_formatter = logging.Formatter(fmt=log_format_file, datefmt="%d.%m.%Y %H:%M:%S")

    cur_time = int(time.time())
    file_handler = logging.FileHandler(f"logs/{cur_time}.log")
    file_handler.setFormatter(file_formatter)

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[console_handler, file_handler]
    )

    for noisy_lib in ("httpx", "httpcore", "urllib3"):
        logger = logging.getLogger(noisy_lib)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False


def main():
    """
    Well, here is where it all starts.

    Like, it really starts here, no jokes 😇
    """
    logger = logging.getLogger(__name__)

    VERSION = "1.0.0-beta"
    GIT_REPO = "https://github.com/IAmScRay/allora_offchain_node_py"

    try:
        with open("./config.json", "r") as config_file:
            CONFIG = json.load(config_file)
    except JSONDecodeError:
        logger.critical("JSONDecodeError: failed to parse `config.json`")
        exit(-1)

    if "debug" in CONFIG:
        setup_logger(CONFIG["debug"])
    else:
        setup_logger(False)

    logger.info("* * * * * * * * * * * * * * * * * * * * * *")
    logger.info("Allora Offchain Node (Python implementation)")
    logger.info(f"Version: {VERSION}")
    logger.info(f"GitHub: {GIT_REPO}")
    logger.info(f"Debugging mode: {'enabled' if CONFIG['debug'] else 'disabled'}")
    logger.info("* * * * * * * * * * * * * * * * * * * * * *")

    if "seed_phrase" not in CONFIG or CONFIG["seed_phrase"] == "":
        logger.critical("Incorrect seed phrase – execution aborted")
        exit(-1)

    if "api_params" not in CONFIG or "api_url" not in CONFIG["api_params"] or CONFIG["api_params"]["api_url"] == "":
        logger.critical("Incorrect API node parameters – execution aborted")
        exit(-1)

    api_node_params = APINodeParams(
        logger=logging.getLogger("API Node"),
        params=CONFIG["api_params"]
    )

    wallet_api_node = APINode(
        params=api_node_params,
        is_wallet_node=True
    )
    if not wallet_api_node.is_connected():
        logger.critical("Wallet's API node client is not connected – execution aborted")
        exit(-1)

    wallet = Wallet(
        seed_phrase=CONFIG["seed_phrase"],
        gas_adjustment=CONFIG["gas_adjustment"],
        api_node=wallet_api_node
    )
    if not wallet.is_initialized():
        logger.critical("Wallet is not initialized – execution aborted")
        exit(-1)

    if "topics" not in CONFIG or len(CONFIG["topics"]) == 0:
        logger.critical("There are no topics to run workers for – execution aborted")
        exit(-1)

    threads = []
    for topic_params in CONFIG["topics"]:
        if "topic_id" not in topic_params:
            logger.critical("`topic_id` field is not present – skipping initializing worker thread...")
            continue

        if "inference_url" not in topic_params:
            logger.critical("`inference_url` field is not present – skipping initializing worker thread...")
            continue

        worker_logger = logging.getLogger(name=f"Worker (topic {topic_params['topic_id']})")
        worker_params = WorkerParams(worker_logger, topic_params)

        thread = Worker(
            wallet=wallet,
            api_node=APINode(
                params=api_node_params,
                is_wallet_node=False
            ),
            worker_params=worker_params
        )

        thread.start()
        threads.append(thread)

    try:
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Interrupt received! Stopping threads...")
        for thread in threads:
            thread.stop()

    for thread in threads:
        thread.join()

    logger.info("Execution finished.")


if __name__ == "__main__":
    main()
