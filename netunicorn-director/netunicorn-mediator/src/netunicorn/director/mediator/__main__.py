import asyncio
import json
import os
from typing import List, Any, Union

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from netunicorn.base.experiment import Experiment
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.resources import get_logger
from returns.pipeline import is_successful
from returns.result import Result

from .engine import (
    cancel_executors,
    cancel_experiment,
    check_services_availability,
    close_db_connection,
    credentials_check,
    experiment_precheck,
    get_experiment_status,
    get_nodes,
    get_experiments,
    delete_experiment,
    open_db_connection,
    prepare_experiment_task,
    start_experiment,
    check_sudo_access,
    check_runtime_context,
)

logger = get_logger("netunicorn.director.mediator")

proxy_path = os.environ.get("PROXY_PATH", "").removesuffix("/")
app = FastAPI(
    title="netunicorn API",
    root_path=proxy_path,
)
security = HTTPBasic()


def result_to_response(result: Result[Any, Any]) -> Response:
    status_code = 200 if is_successful(result) else 400
    content = result.unwrap() if is_successful(result) else result.failure()
    return Response(
        content=json.dumps(content, cls=UnicornEncoder),
        media_type="application/json",
        status_code=status_code,
    )


async def check_credentials(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    current_username = credentials.username
    current_token = credentials.password
    if not await credentials_check(current_username, current_token):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or token",
            headers={"WWW-Authenticate": "Basic"},
        )
    return current_username


@app.exception_handler(Exception)
async def unicorn_exception_handler(_: Request, exc: Exception) -> Response:
    logger.exception(exc)
    return Response(status_code=500, content=str(exc))


@app.get("/health")
async def health_check() -> str:
    await check_services_availability()
    return "OK"


@app.on_event("startup")
async def on_startup() -> None:
    await open_db_connection()
    logger.info("Mediator started, connection to DB established")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_db_connection()
    logger.info("Mediator stopped")


@app.get("/api/v1/nodes", status_code=200)
async def nodes_handler(username: str = Depends(check_credentials)) -> Response:
    return result_to_response(await get_nodes(username))


@app.get("/api/v1/experiment", status_code=200)
async def get_experiments_handler(
    username: str = Depends(check_credentials),
) -> Response:
    return result_to_response(await get_experiments(username))


@app.post(
    "/api/v1/experiment/{experiment_name}/prepare", status_code=200, response_model=None
)
async def prepare_experiment_handler(
    experiment_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Depends(check_credentials),
) -> Union[Response, str]:
    try:
        data = await request.json()
        experiment = Experiment.from_json(data)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't parse experiment from the provided data: {e}",
        )

    prechecks = await asyncio.gather(
        experiment_precheck(experiment),
        check_sudo_access(experiment, username),
        check_runtime_context(experiment),
    )
    for result in prechecks:
        if not is_successful(result):
            return result_to_response(result)

    background_tasks.add_task(
        prepare_experiment_task, experiment_name, experiment, username
    )
    return experiment_name


@app.post("/api/v1/experiment/{experiment_name}/start", status_code=200)
async def start_experiment_handler(
    experiment_name: str, username: str = Depends(check_credentials)
) -> Response:
    result = await start_experiment(experiment_name, username)
    return result_to_response(result)


@app.get("/api/v1/experiment/{experiment_name}", status_code=200)
async def experiment_status_handler(
    experiment_name: str, username: str = Depends(check_credentials)
) -> Response:
    result = await get_experiment_status(experiment_name, username)
    return result_to_response(result)


@app.delete("/api/v1/experiment/{experiment_name}", status_code=200)
async def delete_experiment_handler(
    experiment_name: str, username: str = Depends(check_credentials)
) -> Response:
    result = await delete_experiment(experiment_name, username)
    return result_to_response(result)


@app.post("/api/v1/experiment/{experiment_name}/cancel", status_code=200)
async def cancel_experiment_handler(
    experiment_name: str, username: str = Depends(check_credentials)
) -> Response:
    result = await cancel_experiment(experiment_name, username)
    return result_to_response(result)


@app.post("/api/v1/executors/cancel", status_code=200)
async def cancel_executors_handler(
    executors: List[str], username: str = Depends(check_credentials)
) -> Response:
    result = await cancel_executors(executors, username)
    return result_to_response(result)


if __name__ == "__main__":
    IP = os.environ.get("NETUNICORN_MEDIATOR_IP", "127.0.0.1")
    PORT = int(os.environ.get("NETUNICORN_MEDIATOR_PORT", "26511"))
    logger.info(f"Starting mediator on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)
