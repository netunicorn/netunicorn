import os
import os as _os
import logging as _logging
import redis.asyncio as _redis

# set logger
_logging.basicConfig(level=_logging.INFO)
_name = 'unicorn.director.engine'
logger = _logging.getLogger(_name)
logger.addHandler(_logging.FileHandler(f'{_name}.log'))
logger.setLevel(_logging.INFO)

# connect to redis
REDIS_IP = _os.environ.get('PINOT_REDIS_IP', '127.0.0.1')
REDIS_PORT = int(_os.environ.get('PINOT_REDIS_PORT', '6379'))
logger.info(f"Connecting to Redis on {REDIS_IP}:{REDIS_PORT}")
redis_connection = _redis.Redis(host=REDIS_IP, port=REDIS_PORT, db=0)

# gateway IP and port
# no alternatives, this variable should be defined explicitly to allow minions to connect to the gateway
GATEWAY_IP = os.environ['PINOT_GATEWAY_IP']
if GATEWAY_IP in {'127.0.0.1', '0.0.0.0'}:
    raise Exception(
        f"GATEWAY_IP is {GATEWAY_IP}, which is not allowed. "
        f"Please set it to the IP of the gateway. "
        f"Minions will use this IP to connect to the system and receive tasks."
    )
GATEWAY_PORT = int(os.environ.get('PINOT_GATEWAY_PORT', '26512'))
