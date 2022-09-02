import os
from netunicorn.director.base.resources import get_logger

logger = get_logger('netunicorn.director.mediator')

NETUNICORN_COMPILATION_IP = os.environ.get('NETUNICORN_COMPILATION_IP', '127.0.0.1')
NETUNICORN_COMPILATION_PORT = int(os.environ.get('NETUNICORN_COMPILATION_PORT', '26513'))
logger.info(f"Using compilation service at: {NETUNICORN_COMPILATION_IP}:{NETUNICORN_COMPILATION_PORT}")

NETUNICORN_INFRASTRUCTURE_IP = os.environ.get('NETUNICORN_INFRASTRUCTURE_IP', '127.0.0.1')
NETUNICORN_INFRASTRUCTURE_PORT = int(os.environ.get('NETUNICORN_INFRASTRUCTURE_PORT', '26514'))
logger.info(f"Using infrastructure service at: {NETUNICORN_INFRASTRUCTURE_IP}:{NETUNICORN_INFRASTRUCTURE_PORT}")

NETUNICORN_PROCESSOR_IP = os.environ.get('NETUNICORN_PROCESSOR_IP', '127.0.0.1')
NETUNICORN_PROCESSOR_PORT = int(os.environ.get('NETUNICORN_PROCESSOR_PORT', '26515'))
logger.info(f"Using infrastructure service at: {NETUNICORN_PROCESSOR_IP}:{NETUNICORN_PROCESSOR_PORT}")

DOCKER_REGISTRY_URL = os.environ['NETUNICORN_DOCKER_REGISTRY_URL']  # required
DOCKER_REGISTRY_URL = DOCKER_REGISTRY_URL.removeprefix("http://").removeprefix("https://").removesuffix("/")