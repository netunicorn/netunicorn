import os
from pickle import loads, dumps

import uvicorn
from fastapi import FastAPI, Response, BackgroundTasks, Depends, Request
from fastapi.security import HTTPBasicCredentials, HTTPBasic

from netunicorn.base.experiment import Experiment
from netunicorn.director.base.resources import get_logger, redis_connection

from .engine import get_minion_pool, prepare_experiment_task, start_experiment, get_experiment_status

logger = get_logger('netunicorn.director.gateway')

app = FastAPI()
security = HTTPBasic()


@app.exception_handler(Exception)
async def unicorn_exception_handler(_: Request, exc: Exception):
    logger.exception(exc)
    return Response(status_code=500, content=str(exc))


@app.on_event("startup")
async def on_startup():
    await redis_connection.ping()
    logger.info("Mediator started, connection to Redis established")


@app.on_event("shutdown")
async def on_shutdown():
    await redis_connection.close()
    logger.info("Mediator stopped")


@app.get("/api/v1/minion_pool", status_code=200)
async def minion_pool_handler(credentials: HTTPBasicCredentials = Depends(security)):
    return await get_minion_pool(credentials.username)


@app.post("/api/v1/experiment/{experiment_name}/prepare", status_code=200)
async def prepare_experiment_handler(
        experiment_name: str, experiment: bytes,
        background_tasks: BackgroundTasks, credentials: HTTPBasicCredentials = Depends(security)
):
    experiment = loads(experiment)
    if not isinstance(experiment, Experiment):
        logger.debug(experiment)
        raise Exception(f"Invalid payload provided of type {type(experiment)}")

    background_tasks.add_task(prepare_experiment_task, experiment_name, experiment, credentials.username)
    return experiment_name


@app.post("/api/v1/experiment/{experiment_name}/start", status_code=200)
async def start_experiment_handler(experiment_name: str, credentials: HTTPBasicCredentials = Depends(security)):
    await start_experiment(experiment_name, credentials.username)
    return experiment_name


@app.get("/api/v1/experiment/{experiment_name}", status_code=200)
async def experiment_status_handler(experiment_name: str, credentials: HTTPBasicCredentials = Depends(security)):
    return dumps(await get_experiment_status(experiment_name, credentials.username))


if __name__ == '__main__':
    IP = os.environ.get('NETUNICORN_MEDIATOR_IP', '0.0.0.0')
    PORT = int(os.environ.get('NETUNICORN_MEDIATOR_PORT', '26512'))
    logger.info(f"Starting mediator on {IP}, {PORT}")
    uvicorn.run(app, host=IP, port=PORT)