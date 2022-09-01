import pickle
from base64 import b64decode

from fastapi import FastAPI, BackgroundTasks
from netunicorn.base.experiment import Experiment
from pydantic import BaseModel
import uvicorn

from .deployer_connectors.salt_connector import SaltConnector

app = FastAPI()
connector = SaltConnector()


class DeploymentStartRequest(BaseModel):
    uid: str
    experiment: bytes


@app.get("/minions")
async def get_minion_pool():
    return pickle.dumps(await connector.get_minion_pool())


@app.post("/start_deployment")
async def start_deployment(data: DeploymentStartRequest, background_tasks: BackgroundTasks):
    experiment: Experiment = pickle.loads(b64decode(data.experiment))
    background_tasks.add_task(connector.start_deployment, experiment, data.uid)
    return {"result": "success"}


@app.post("/start_execution/{uid}")
async def start_execution(uid: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_execution, uid)
    return {"result": "success"}


uvicorn.run(app, host="0.0.0.0", port=26514)
