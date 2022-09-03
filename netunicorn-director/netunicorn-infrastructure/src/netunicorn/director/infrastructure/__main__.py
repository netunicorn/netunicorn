import pickle

from fastapi import FastAPI, BackgroundTasks, Response
import uvicorn

from .deployer_connectors.salt_connector import SaltConnector

app = FastAPI()
connector = SaltConnector()


@app.get("/minions")
async def get_minion_pool():
    return Response(content=pickle.dumps(await connector.get_minion_pool()), status_code=200)


@app.post("/start_deployment/{experiment_id}")
async def start_deployment(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_deployment, experiment_id)
    return {"result": "success"}


@app.post("/start_execution/{experiment_id}")
async def start_execution(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(connector.start_execution, experiment_id)
    return {"result": "success"}


uvicorn.run(app, host="0.0.0.0", port=26514)
