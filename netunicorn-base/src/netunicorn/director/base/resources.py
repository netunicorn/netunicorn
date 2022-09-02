import logging as __logging
import os as __os
import redis.asyncio as __redis

__logging.basicConfig()

__REDIS_IP = __os.environ.get('NETUNICORN_REDIS_IP', '127.0.0.1')
__REDIS_PORT = int(__os.environ.get('NETUNICORN_REDIS_PORT', '6379'))
__logging.info(f"Connecting to Redis on {__REDIS_IP}:{__REDIS_PORT}")
redis_connection = __redis.Redis(host=__REDIS_IP, port=__REDIS_PORT, db=0)

__logging_levels = {
    'DEBUG': __logging.DEBUG,
    'INFO': __logging.INFO,
    'WARNING': __logging.WARNING,
    'ERROR': __logging.ERROR,
    'CRITICAL': __logging.CRITICAL,
}

__logger_level = __os.environ.get('NETUNICORN_LOG_LEVEL', 'INFO')
__logger_level = __logging_levels.get(__logger_level, __logging.INFO)


def get_logger(name: str, level: int = __logger_level) -> __logging.Logger:
    logger = __logging.getLogger(name)
    logger.addHandler(__logging.FileHandler(f'{name}.log'))
    logger.setLevel(level)
    return logger
