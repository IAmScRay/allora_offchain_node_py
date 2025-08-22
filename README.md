# Allora Offchain Node (Python implementation)

## What is this? 🧐
This repo contains a Python implementation of an offchain worker node for Allora Network. There is an official Go implementation [here](https://github.com/allora-network/allora-offchain-node) that has a lot of customization and versatility, and it can run a reputer too, but after speaking with ML devs who want to run a model that contributes to the network, they have had tough times deploying and running worker nodes.

Since this project consists of worker implementation only, it has the easiest setup possible when you want to start contributing to the collective intelligence Allora is all about right away.

## How do I configure this thing? 🤔
There is `config.json` in this repo that is used for configuration. It looks like this:

```json
{
  "debug": false,  <-- this enables / disables debug messages in the logs
  "seed_phrase": "",  <-- your worker wallet's seed phrase & you MUST fund this wallet before running a worker node
  "api_params": {
    "api_url": "",  <-- URL to an API (LCD) blockchain node (e.g. https://api.testnet.allora.network for Allora Testnet)
    "tx_check_retries": 15,
    "tx_check_freq": 3
  },
  "topics": [
    {
      "topic_id": 1,  <-- ID of a topic you want to run a worker for
      "inference_url": "http://localhost:8000/ETH",  <-- URL where your worker will fetch inferences from
      "nonce_fetch_freq": 3,
      "inference_fetch_retries": 10,
      "inference_fetch_retry_freq": 3
    }
  ]
}

```
Let's go step-by-step with each section.

### ``api_params``
This section is about parameters of a blockchain API node. You **MUST** populate `api_url` there with a URL to an API (LCD) blockchain node, starting with `http(s)://...`, other parameters are non-critical & have their default values built in inside of worker's logic.

`tx_check_retries` refers to the number of retries when worker checks if an inference transaction is included in a block. Since it may not (and it just logically cannot) be instantaneous, worker has to try & fetch a transaction receipt.

`tx_check_freq` refers to the interval in seconds between each transaction check retry.

### ``topics``
This section is about topic worker runs for. You can add as many topic objects as you want.

`topic_id` - well, it's self-explanatory. You can see all existing topic IDs [here](https://docs.allora.network/devs/get-started/existing-topics), or, if you are participating in the Model Forge competition – [here](https://forge.allora.network/competitions).

`inference_url` is a URL to an inference endpoint worker will try to fetch an inference value from.

`nonce_fetch_freq` refers to the interval in seconds worker tries to fetch an open inference submission nonce from the chain.

`inference_fetch_retries` refers to the number of retries when worker tries to fetch an inference & fails to do so (for the number of reasons like inference endpoint maintenance or it has crashed).

`inference_fetch_retry_freq` refers to the interval in seconds between each inference fetch retry.

If you want to add another topic, simply add a new object, and you **MUST** populate `topic_id` and `inference_url` fields for correct operation; other fields are non-critical and have default values in the code. Adding a new topic looks like this:

```json
 "topics": [
    {
      "topic_id": 1, 
      "inference_url": "http://localhost:8000/ETH",
      "nonce_fetch_freq": 3,
      "inference_fetch_retries": 10,
      "inference_fetch_retry_freq": 3
    },
    {
      "topic_id": 3,  <-- new topic ID
      "inference_url": "http://localhost:8000/BTC"  <-- new inference URL
    }
  ]
```

❗️ If you plan to use the worker and inference endpoint on the same server & you decide to run worker using Docker, make sure you set IP address `http://host.docker.internal:...` for correct inference fetching.

## Let's run! 🚀
There are 2 ways to run this worker: using Docker or natively with `python3`.

### Docker (using `docker-compose`)
1. Make sure you have Docker & Docker Compose plugin installed by running `docker -v` and `docker-compose -v`. Head over to https://docs.docker.com/engine/install/ and https://docs.docker.com/compose/ in case you need to install them.
2. Clone this repo and go to its directory (if you have not already): `git clone https://github.com/IAmScRay/allora_offchain_node_py && cd allora_offchain_node_py`
3. Make all appropriate changes to `config.json` & don't forget to save the file.
4. Run `docker-compose up -d --build` to build a Docker image and start the worker.

You can see container logs using `docker-compose logs -f` inside worker's folder. Also, `logs` folder is created where all `.log` files are saved if needed.

To stop the worker, run `docker-compose down` inside worker's folder.

### Native Python
1. Make sure you have Python 3.11+ installed on your machine. Head over to https://www.python.org/downloads/ in case you don't have it.
2. Run `apt-get update && apt-get upgrade -y && apt-get install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev curl libbz2-dev liblzma-dev`. This updates packages on your machine and installs necessary utilities for building all dependencies worker needs to function properly.
3. Clone this repo and go to its directory (if you have not already): `git clone https://github.com/IAmScRay/allora_offchain_node_py && cd allora_offchain_node_py`
4. Make all appropriate changes to `config.json` & don't forget to save the file.
5. We will run the worker in the background using `tmux`. Create a new `tmux` session like so: `tmux new -s <session_name>`
6. Create and activate a virtual environment: `python3 -m venv venv && source venv/bin/activate`
7. Install dependencies: `pip install -r requirements.txt`
8. Run `python3 main.py` to start the worker.

To stop the worker, press `Ctrl + C` inside of worker's terminal.

If you want to get back to your main terminal, press `Ctrl + B`, then switfly press `D`. If you want to get back to the worker's terminal, use `tmux attach -t <session_name>`.

## License
This project is licensed under the MIT License - see the [LICENSE](https://github.com/IAmScRay/allora_offchain_node_py/blob/main/LICENSE) file for details.
