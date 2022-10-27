import os

from netunicorn.director.base.resources import get_logger

logger = get_logger("netunicorn.director.mediator")

NETUNICORN_COMPILATION_ENDPOINT = os.environ.get(
    "NETUNICORN_COMPILATION_ENDPOINT", "http://127.0.0.1:26513"
)
logger.info(f"Using compilation service at: {NETUNICORN_COMPILATION_ENDPOINT}")

NETUNICORN_INFRASTRUCTURE_ENDPOINT = os.environ.get(
    "NETUNICORN_INFRASTRUCTURE_ENDPOINT", "http://127.0.0.1:26514"
)
logger.info(f"Using infrastructure service at: {NETUNICORN_INFRASTRUCTURE_ENDPOINT}")

NETUNICORN_PROCESSOR_ENDPOINT = os.environ.get(
    "NETUNICORN_PROCESSOR_ENDPOINT", "http://127.0.0.1:26515"
)
logger.info(f"Using infrastructure service at: {NETUNICORN_PROCESSOR_ENDPOINT}")

NETUNICORN_AUTH_ENDPOINT = os.environ.get(
    "NETUNICORN_AUTH_ENDPOINT", "http://127.0.0.1:26516"
)
logger.info(f"Using authorization service at: {NETUNICORN_AUTH_ENDPOINT}")

DOCKER_REGISTRY_URL = os.environ["NETUNICORN_DOCKER_REGISTRY_URL"]  # required
# DOCKER_REGISTRY_URL = DOCKER_REGISTRY_URL.removeprefix("http://").removeprefix("https://").removesuffix("/")
