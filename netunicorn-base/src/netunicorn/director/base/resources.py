import logging as __logging
import os as __os
import sys

__logging.basicConfig()

DATABASE_ENDPOINT = __os.environ.get("NETUNICORN_DATABASE_ENDPOINT", None)
DATABASE_ENDPOINT_DEFAULT = False
if DATABASE_ENDPOINT is None:
    DATABASE_ENDPOINT_DEFAULT = True
    DATABASE_ENDPOINT = "127.0.0.1"

DATABASE_USER = __os.environ.get("NETUNICORN_DATABASE_USER", None)
DATABASE_USER_DEFAULT = False
if DATABASE_USER is None:
    DATABASE_USER_DEFAULT = True
    DATABASE_USER = "unicorn"

DATABASE_PASSWORD = __os.environ.get("NETUNICORN_DATABASE_PASSWORD")

DATABASE_DB = __os.environ.get("NETUNICORN_DATABASE_DB", None)
DATABASE_DB_DEFAULT = False
if DATABASE_DB is None:
    DATABASE_DB_DEFAULT = True
    DATABASE_DB = "unicorndb"

__logging.info(f"Connecting to {DATABASE_ENDPOINT}/{DATABASE_DB} as {DATABASE_USER}")

LOGGING_LEVELS = {
    "DEBUG": __logging.DEBUG,
    "INFO": __logging.INFO,
    "WARNING": __logging.WARNING,
    "ERROR": __logging.ERROR,
    "CRITICAL": __logging.CRITICAL,
}

__logger_level_ = __os.environ.get("NETUNICORN_LOG_LEVEL", "INFO").upper()
__logger_level = LOGGING_LEVELS.get(__logger_level_, __logging.INFO)


def get_logger(name: str, level: int = __logger_level) -> __logging.Logger:
    formatter = __logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = __logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False

    stream_handler = __logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    file_handler = __logging.FileHandler(f"{name}.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    logger.setLevel(level)
    logger.info(f"Logger {name} created with level {level}")
    return logger
