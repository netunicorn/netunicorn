import os
from netunicorn.director.base.resources import get_logger, \
    DATABASE_ENDPOINT, DATABASE_USER, DATABASE_PASSWORD, DATABASE_DB

# set logger
logger = get_logger('netunicorn.director.infrastructure')

# gateway IP and port
# no alternatives, this variable should be defined explicitly to allow minions to connect to the gateway
GATEWAY_ENDPOINT = os.environ['NETUNICORN_GATEWAY_ENDPOINT']
