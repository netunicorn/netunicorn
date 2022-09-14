from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import Response
import uvicorn

import json
from netunicorn.base.utils import UnicornEncoder
from .deployer_connectors.salt_connector import SaltConnector
from .resources import redis_connection

app = FastAPI()
connector = SaltConnector()


@app.get('/health')
async def health_check() -> str:
    await redis_connection.ping()
    return 'OK'


@app.on_event("startup")
async def startup():
    await redis_connection.ping()


@app.on_event("shutdown")
async def shutdown():
    await redis_connection.close()


@app.get("/minions", status_code=200)
async def get_minion_pool():
    return Response(content=json.dumps(await connector.get_minion_pool(), cls=UnicornEncoder), media_type="application/json")


@app.post("/start_deployment/{experiment_id}")
async def start_deployment(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_deployment, experiment_id)
    return {"result": "success"}


@app.post("/start_execution/{experiment_id}")
async def start_execution(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_execution, experiment_id)
    return {"result": "success"}


uvicorn.run(app, host="127.0.0.1", port=26514)
