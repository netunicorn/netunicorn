import uvicorn
from pinot.director.gateway.api import app, GATEWAY_IP, GATEWAY_PORT

# noinspection PyTypeChecker
uvicorn.run(app, host=GATEWAY_IP, port=GATEWAY_PORT)
