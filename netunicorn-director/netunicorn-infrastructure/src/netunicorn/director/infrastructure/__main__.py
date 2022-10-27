import json
from typing import List

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import Response
from netunicorn.base.utils import UnicornEncoder

from .deployer_connectors.salt_connector import SaltConnector

app = FastAPI()
connector = SaltConnector()


@app.get("/health")
async def health_check() -> str:
    await connector.healthcheck()
    return "OK"


@app.on_event("startup")
async def startup():
    await connector.on_startup()


@app.on_event("shutdown")
async def shutdown():
    await connector.on_shutdown()


@app.get("/minions", status_code=200)
async def get_minion_pool():
    return Response(
        content=json.dumps(await connector.get_minion_pool(), cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/start_deployment/{experiment_id}")
async def start_deployment(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_deployment, experiment_id)
    return {"result": "success"}


@app.post("/start_execution/{experiment_id}")
async def start_execution(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_execution, experiment_id)
    return {"result": "success"}


@app.post("/cancel_executors")
async def cancel_executors(executors: List[str], background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.cancel_executors, executors)
    return {"result": "success"}


uvicorn.run(app, host="127.0.0.1", port=26514)
