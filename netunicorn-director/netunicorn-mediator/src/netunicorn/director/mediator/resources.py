import os
from netunicorn.director.base.resources import get_logger

logger = get_logger('netunicorn.director.mediator')

NETUNICORN_COMPILATION_ENDPOINT = os.environ.get('NETUNICORN_COMPILATION_ENDPOINT', '127.0.0.1:26513')
logger.info(f"Using compilation service at: {NETUNICORN_COMPILATION_ENDPOINT}")

NETUNICORN_INFRASTRUCTURE_ENDPOINT = os.environ.get('NETUNICORN_INFRASTRUCTURE_ENDPOINT', '127.0.0.1:26514')
logger.info(f"Using infrastructure service at: {NETUNICORN_INFRASTRUCTURE_ENDPOINT}")

NETUNICORN_PROCESSOR_ENDPOINT = os.environ.get('NETUNICORN_PROCESSOR_ENDPOINT', '127.0.0.1:26515')
logger.info(f"Using infrastructure service at: {NETUNICORN_PROCESSOR_ENDPOINT}")

DOCKER_REGISTRY_URL = os.environ['NETUNICORN_DOCKER_REGISTRY_URL']  # required

# TODO: enable when mediator layer would work on Python 3.9
# DOCKER_REGISTRY_URL = DOCKER_REGISTRY_URL.removeprefix("http://").removeprefix("https://").removesuffix("/")