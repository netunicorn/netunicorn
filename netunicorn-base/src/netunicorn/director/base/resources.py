import logging as __logging
import os as __os
import sys

import redis.asyncio as __redis

__logging.basicConfig()

__redis_endpoint = __os.environ.get('NETUNICORN_REDIS_ENDPOINT', '127.0.0.1:6379')
__redis_host, __redis_port = __redis_endpoint.split(':')
__logging.info(f"Connecting to Redis on {__redis_endpoint}")
redis_connection = __redis.Redis(host=__redis_host, port=__redis_port, db=0)

__logging_levels = {
    'DEBUG': __logging.DEBUG,
    'INFO': __logging.INFO,
    'WARNING': __logging.WARNING,
    'ERROR': __logging.ERROR,
    'CRITICAL': __logging.CRITICAL,
}

__logger_level = __os.environ.get('NETUNICORN_LOG_LEVEL', 'INFO').upper()
__logger_level = __logging_levels.get(__logger_level, __logging.INFO)


def get_logger(name: str, level: int = __logger_level) -> __logging.Logger:
    formatter = __logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logger = __logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False

    stream_handler = __logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = __logging.FileHandler(f'{name}.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.setLevel(level)
    logger.info(f"Logger {name} created with level {level}")
    return logger
