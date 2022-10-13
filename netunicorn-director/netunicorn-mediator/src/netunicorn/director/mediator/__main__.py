import json
import os
from typing import List

import uvicorn
from fastapi import FastAPI, Response, BackgroundTasks, Depends, Request, HTTPException
from fastapi.security import HTTPBasicCredentials, HTTPBasic

from netunicorn.base.experiment import Experiment
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.resources import get_logger

from .engine import get_minion_pool, prepare_experiment_task, start_experiment, get_experiment_status, \
    check_services_availability, credentials_check, open_db_connection, close_db_connection, \
    cancel_experiment, cancel_executors, experiment_precheck

logger = get_logger('netunicorn.director.mediator')

app = FastAPI()
security = HTTPBasic()


async def check_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    current_username = credentials.username
    current_token = credentials.password
    if not await credentials_check(current_username, current_token):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or token",
            headers={"WWW-Authenticate": "Basic"}
        )
    return current_username


@app.exception_handler(Exception)
async def unicorn_exception_handler(_: Request, exc: Exception):
    logger.exception(exc)
    return Response(status_code=500, content=str(exc))


@app.get('/health')
async def health_check() -> str:
    await check_services_availability()
    return 'OK'


@app.on_event("startup")
async def on_startup():
    await open_db_connection()
    logger.info("Mediator started, connection to DB established")


@app.on_event("shutdown")
async def on_shutdown():
    await close_db_connection()
    logger.info("Mediator stopped")


@app.get("/api/v1/minion_pool", status_code=200)
async def minion_pool_handler(username: str = Depends(check_credentials)):
    return await get_minion_pool(username)


@app.post("/api/v1/experiment/{experiment_name}/prepare", status_code=200)
async def prepare_experiment_handler(
        experiment_name: str,
        request: Request,
        background_tasks: BackgroundTasks,
        username: str = Depends(check_credentials)
):
    try:
        data = await request.json()
        experiment = Experiment.from_json(data)
    except Exception as e:
        logger.exception(e)
        raise Exception(f"Couldn't parse experiment from the provided data: {e}")

    result, error = experiment_precheck(experiment)
    if not result:
        raise Exception(f"Experiment precheck failed: {error}")
    background_tasks.add_task(prepare_experiment_task, experiment_name, experiment, username)
    return experiment_name


@app.post("/api/v1/experiment/{experiment_name}/start", status_code=200)
async def start_experiment_handler(experiment_name: str, username: str = Depends(check_credentials)):
    await start_experiment(experiment_name, username)
    return experiment_name


@app.get("/api/v1/experiment/{experiment_name}", status_code=200)
async def experiment_status_handler(experiment_name: str, username: str = Depends(check_credentials)):
    return Response(
        content=json.dumps(await get_experiment_status(experiment_name, username), cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/api/v1/experiment/{experiment_name}/cancel", status_code=200)
async def cancel_experiment_handler(experiment_name: str, username: str = Depends(check_credentials)):
    return await cancel_experiment(experiment_name, username)


@app.post("/api/v1/executors/cancel", status_code=200)
async def cancel_executors_handler(executors: List[str], username: str = Depends(check_credentials)):
    return await cancel_executors(executors, username)


if __name__ == '__main__':
    IP = os.environ.get('NETUNICORN_MEDIATOR_IP', '127.0.0.1')
    PORT = int(os.environ.get('NETUNICORN_MEDIATOR_PORT', '26511'))
    logger.info(f"Starting mediator on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)
