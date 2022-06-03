import os
import os as _os
import logging as _logging
import redis as _redis

from pinot.director.engine.config import ConnectorClass as Connector

# set logger
_logging.basicConfig(level=_logging.INFO)
_name = 'pinot.director.engine'
logger = _logging.getLogger(_name)
logger.addHandler(_logging.FileHandler(f'{_name}.log'))
logger.setLevel(_logging.INFO)

# set deployer connector
deployer_connector = Connector()

# connect to redis
REDIS_IP = _os.environ.get('PINOT_REDIS_IP', '127.0.0.1')
REDIS_PORT = int(_os.environ.get('PINOT_REDIS_PORT', '6379'))
logger.info(f"Connecting to Redis on {REDIS_IP}:{REDIS_PORT}")
redis_connection = _redis.Redis(host=REDIS_IP, port=REDIS_PORT, db=0)

# gateway IP and port
# no alternatives, this variable should be defined explicitly to allow minions to connect to the gateway
GATEWAY_IP = os.environ['PINOT_GATEWAY_IP']
GATEWAY_PORT = int(os.environ.get('PINOT_GATEWAY_PORT', '26512'))