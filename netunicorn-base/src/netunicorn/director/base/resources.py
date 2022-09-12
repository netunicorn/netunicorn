import logging as __logging
import os as __os
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
    logger = __logging.getLogger(name)
    logger.addHandler(__logging.FileHandler(f'{name}.log'))
    logger.setLevel(level)
    logger.info(f"Logger {name} created with level {level}")
    return logger
