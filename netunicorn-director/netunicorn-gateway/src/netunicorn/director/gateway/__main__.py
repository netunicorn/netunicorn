import uvicorn

from .api import GATEWAY_IP, GATEWAY_PORT, app

# noinspection PyTypeChecker
uvicorn.run(app, host=GATEWAY_IP, port=GATEWAY_PORT)
