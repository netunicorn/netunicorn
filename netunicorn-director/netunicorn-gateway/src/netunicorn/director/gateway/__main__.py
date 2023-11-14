import uvicorn

from .api import GATEWAY_IP, GATEWAY_PORT, app

log_config = uvicorn.config.LOGGING_CONFIG
log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"

# noinspection PyTypeChecker
uvicorn.run(app, host=GATEWAY_IP, port=GATEWAY_PORT)
