import os
from netunicorn.director.base.resources import get_logger, redis_connection

# set logger
logger = get_logger('netunicorn.director.infrastructure')
redis_connection = redis_connection

# gateway IP and port
# no alternatives, this variable should be defined explicitly to allow minions to connect to the gateway
GATEWAY_IP = os.environ['NETUNICORN_GATEWAY_IP']
if GATEWAY_IP in {'127.0.0.1', '0.0.0.0'}:
    raise Exception(
        f"GATEWAY_IP is {GATEWAY_IP}, which is not allowed. "
        f"Please set it to the IP of the gateway. "
        f"Minions will use this IP to connect to the system and receive tasks."
    )
GATEWAY_PORT = int(os.environ.get('NETUNICORN_GATEWAY_PORT', '26512'))
