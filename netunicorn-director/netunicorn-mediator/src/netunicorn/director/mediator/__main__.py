import asyncio
import json
import os
from typing import Annotated, Any, List, Optional, Union

import uvicorn
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from netunicorn.base.experiment import Experiment
from netunicorn.base.types import FlagValues
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.resources import get_logger
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result

from .engine import (
    cancel_executors,
    cancel_experiment,
    check_runtime_context,
    check_services_availability,
    check_sudo_access,
    close_db_connection,
    credentials_check,
    delete_experiment,
    experiment_precheck,
    get_experiment_flag,
    get_experiment_status,
    get_experiments,
    get_nodes,
    open_db_connection,
    prepare_experiment_task,
    set_experiment_flag,
    start_experiment,
)


class CancellationRequest(BaseModel):
    executors: List[str]
    cancellation_context: Optional[dict[str, dict[str, str]]] = None


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


async def parse_context(json_str: Optional[str]) -> Any:
    if not json_str or json_str == "null":
        return None
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.exception(e)
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't parse the context: {e}",
        )


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
async def nodes_handler(
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    return result_to_response(
        await get_nodes(username, await parse_context(netunicorn_auth_context))
    )


@app.get("/api/v1/experiment", status_code=200)
async def get_experiments_handler(
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    _ = netunicorn_auth_context  # unused
    return result_to_response(await get_experiments(username))


@app.post(
    "/api/v1/experiment/{experiment_name}/prepare", status_code=200, response_model=None
)
async def prepare_experiment_handler(
    experiment_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Union[Response, str]:
    netunicorn_auth_context_parsed = await parse_context(netunicorn_auth_context)
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
        prepare_experiment_task,
        experiment_name,
        experiment,
        username,
        netunicorn_auth_context_parsed,
    )
    return experiment_name


@app.post("/api/v1/experiment/{experiment_name}/start", status_code=200)
async def start_experiment_handler(
    experiment_name: str,
    username: str = Depends(check_credentials),
    execution_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    netunicorn_auth_context_parsed = await parse_context(netunicorn_auth_context)
    result = await start_experiment(
        experiment_name, username, execution_context, netunicorn_auth_context_parsed
    )
    return result_to_response(result)


@app.get("/api/v1/experiment/{experiment_name}", status_code=200)
async def experiment_status_handler(
    experiment_name: str,
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    _ = netunicorn_auth_context  # unused
    result = await get_experiment_status(experiment_name, username)
    return result_to_response(result)


@app.delete("/api/v1/experiment/{experiment_name}", status_code=200)
async def delete_experiment_handler(
    experiment_name: str,
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    _ = netunicorn_auth_context  # unused
    result = await delete_experiment(experiment_name, username)
    return result_to_response(result)


@app.post("/api/v1/experiment/{experiment_name}/cancel", status_code=200)
async def cancel_experiment_handler(
    experiment_name: str,
    username: str = Depends(check_credentials),
    cancellation_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    netunicorn_auth_context_parsed = await parse_context(netunicorn_auth_context)
    result = await cancel_experiment(
        experiment_name,
        username,
        cancellation_context,
        netunicorn_auth_context_parsed,
    )
    return result_to_response(result)


@app.post("/api/v1/executors/cancel", status_code=200)
async def cancel_executors_handler(
    data: CancellationRequest,
    username: str = Depends(check_credentials),
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    netunicorn_auth_context_parsed = await parse_context(netunicorn_auth_context)
    result = await cancel_executors(
        data.executors,
        username,
        data.cancellation_context,
        netunicorn_auth_context_parsed,
    )
    return result_to_response(result)


@app.get("/api/v1/experiment/{experiment_id}/flag/{flag_name}", status_code=200)
async def get_experiment_flag_handler(
    experiment_id: str,
    flag_name: str,
    username: str = Depends(check_credentials),
) -> Response:
    result = await get_experiment_flag(username, experiment_id, flag_name)
    return result_to_response(result.map(lambda x: x.dict()))


@app.post("/api/v1/experiment/{experiment_id}/flag/{flag_name}", status_code=204)
async def set_experiment_flag_handler(
    experiment_id: str,
    flag_name: str,
    username: str = Depends(check_credentials),
    values: FlagValues = Body(...),
) -> Response:
    result = await set_experiment_flag(username, experiment_id, flag_name, values)
    return result_to_response(result)


if __name__ == "__main__":
    IP = os.environ.get("NETUNICORN_MEDIATOR_IP", "0.0.0.0")
    PORT = int(os.environ.get("NETUNICORN_MEDIATOR_PORT", "26511"))
    logger.info(f"Starting mediator on {IP}:{PORT}")
    uvicorn.run(app, host=IP, port=PORT)
