import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, List, Optional, Union
from datetime import timedelta

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
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from netunicorn.base.experiment import Experiment
from netunicorn.base.types import FlagValues
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.resources import get_logger
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result

from .admin import admin_page
from .engine import (
    generate_access_token,
    verify_access_token,
    cancel_executors,
    cancel_experiment,
    check_environments,
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
security = OAuth2PasswordBearer(tokenUrl="token")


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    await open_db_connection()
    logger.info("Mediator started, connection to DB established")
    yield
    await close_db_connection()
    logger.info("Mediator stopped")


app = FastAPI(title="netunicorn API", root_path=proxy_path, lifespan=lifespan)


def result_to_response(result: Result[Any, Any]) -> Response:
    status_code = 200 if is_successful(result) else 400
    content = result.unwrap() if is_successful(result) else result.failure()
    if status_code == 400:
        logger.warning(f"Returning error response: {content}")
    return Response(
        content=json.dumps(content, cls=UnicornEncoder),
        media_type="application/json",
        status_code=status_code,
    )


async def verify_token(token: Annotated[str, Depends(security)]) -> str:
    username = await verify_access_token(token)
    if not is_successful(username):
        raise HTTPException(
            status_code=401,
            detail=username.failure(),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username.unwrap()


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    username = form_data.username
    password = form_data.password

    if not await credentials_check(username, password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = await generate_access_token(username, expiration=timedelta(days=1))
    if not is_successful(token):
        raise HTTPException(
            status_code=401,
            detail=token.failure(),
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"access_token": token.unwrap(), "token_type": "bearer"}


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


@app.get("/verify_token")
async def verify_token_handler(
    _: Annotated[str, Depends(verify_token)],
) -> Response:
    return Response(status_code=200)


@app.get("/health")
async def health_check(_: Annotated[str, Depends(verify_token)]) -> str:
    await check_services_availability()
    return "OK"


@app.get("/api/v1/nodes", status_code=200)
async def nodes_handler(
    username: Annotated[str, Depends(verify_token)],
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    return result_to_response(
        await get_nodes(username, await parse_context(netunicorn_auth_context))
    )


@app.get("/api/v1/experiment", status_code=200)
async def get_experiments_handler(
    username: Annotated[str, Depends(verify_token)],
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
    username: Annotated[str, Depends(verify_token)],
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
        check_environments(experiment),
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
    username: Annotated[str, Depends(verify_token)],
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
    username: Annotated[str, Depends(verify_token)],
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    _ = netunicorn_auth_context  # unused
    result = await get_experiment_status(experiment_name, username)
    return result_to_response(result)


@app.delete("/api/v1/experiment/{experiment_name}", status_code=200)
async def delete_experiment_handler(
    experiment_name: str,
    username: Annotated[str, Depends(verify_token)],
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    _ = netunicorn_auth_context  # unused
    result = await delete_experiment(experiment_name, username)
    return result_to_response(result)


@app.post("/api/v1/experiment/{experiment_name}/cancel", status_code=200)
async def cancel_experiment_handler(
    experiment_name: str,
    username: Annotated[str, Depends(verify_token)],
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
    username: Annotated[str, Depends(verify_token)],
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
    username: Annotated[str, Depends(verify_token)],
) -> Response:
    result = await get_experiment_flag(username, experiment_id, flag_name)
    return result_to_response(result.map(lambda x: x.dict()))


@app.post("/api/v1/experiment/{experiment_id}/flag/{flag_name}", status_code=204)
async def set_experiment_flag_handler(
    experiment_id: str,
    flag_name: str,
    username: Annotated[str, Depends(verify_token)],
    values: FlagValues = Body(...),
) -> Response:
    result = await set_experiment_flag(username, experiment_id, flag_name, values)
    return result_to_response(result)


@app.get("/admin", response_class=HTMLResponse)
async def get_admin_page(
    request: Request,
    username: Annotated[str, Depends(verify_token)],
    days: Optional[int] = 7,
) -> Response:
    return await admin_page(request, username, days)


if __name__ == "__main__":
    IP = os.environ.get("NETUNICORN_MEDIATOR_IP", "0.0.0.0")
    PORT = int(os.environ.get("NETUNICORN_MEDIATOR_PORT", "26511"))
    logger.info(f"Starting mediator on {IP}:{PORT}")

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s - %(levelname)s - %(message)s"
    log_config["formatters"]["default"][
        "fmt"
    ] = "%(asctime)s - %(levelname)s - %(message)s"
    uvicorn.run(app, host=IP, port=PORT)
