import os
from pickle import loads, dumps

import uvicorn
from fastapi import FastAPI, Response, BackgroundTasks
from netunicorn.base.experiment import Experiment

from netunicorn.director.base.resources import get_logger, redis_connection

from .engine import get_minion_pool, prepare_experiment_task, start_experiment_task, get_experiment_status, \
    get_experiment_result

logger = get_logger('netunicorn.director.gateway')

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    await redis_connection.ping()
    logger.info("Mediator started, connection to Redis established")


@app.on_event("shutdown")
async def on_shutdown():
    await redis_connection.close()
    logger.info("Mediator stopped")


@app.get("/api/v1/minion_pool", status_code=200)
async def minion_pool():
    try:
        return await get_minion_pool()
    except Exception as e:
        logger.exception(e)
        return Response(status_code=500, content=str(e))


@app.post("/api/v1/experiment/{experiment_id}/prepare", status_code=200)
async def prepare_experiment(experiment_id: str, experiment: bytes, background_tasks: BackgroundTasks):
    try:
        experiment = loads(experiment)
        if not isinstance(experiment, Experiment):
            logger.debug(experiment)
            raise Exception(f"Invalid payload provided of type {type(experiment)}")

        background_tasks.add_task(prepare_experiment_task, experiment_id, experiment)
        return experiment_id
    except Exception as e:
        logger.exception(e)
        return Response(status_code=500, content=str(e))


@app.post("/api/v1/experiment/{experiment_id}/start", status_code=200)
async def start_experiment(experiment_id: str, background_tasks: BackgroundTasks):
    background_tasks.add_task(start_experiment_task, experiment_id)
    return experiment_id


@app.get("/api/v1/experiment/{experiment_id}", status_code=200)
async def experiment_status(experiment_id: str):
    try:
        return dumps(await get_experiment_status(experiment_id))
    except Exception as e:
        logger.exception(e)
        return Response(status_code=500, content=str(e))


@app.get("/api/v1/experiment/{experiment_id}/result", status_code=200)
async def experiment_result(experiment_id: str):
    try:
        return dumps(await get_experiment_result(experiment_id))
    except Exception as e:
        logger.exception(e)
        return Response(status_code=500, content=str(e))


if __name__ == '__main__':
    IP = os.environ.get('NETUNICORN_MEDIATOR_IP', '0.0.0.0')
    PORT = int(os.environ.get('NETUNICORN_MEDIATOR_PORT', '26512'))
    logger.info(f"Starting mediator on {IP}, {PORT}")
    uvicorn.run(app, host=IP, port=PORT)
