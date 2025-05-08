import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any, Dict, List, Optional, Union
import importlib

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
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from netunicorn.base.experiment import Experiment, ExperimentStatus, DeploymentExecutionResult
from netunicorn.base.types import FlagValues
from netunicorn.base.utils import UnicornEncoder
from netunicorn.base.nodes import Node, Architecture
from netunicorn.director.base.resources import get_logger
from pydantic import BaseModel
from returns.pipeline import is_successful
from returns.result import Result

from .engine import (
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
    generate_access_token,
    get_experiment_flag,
    get_experiment_status,
    get_experiments,
    get_nodes,
    get_pipelines,
    open_db_connection,
    prepare_experiment_task,
    set_experiment_flag,
    start_experiment,
    verify_access_token,
)
from .ui_api import (
    get_active_compilations,
    get_last_experiments,
    get_locked_nodes,
    get_running_experiments,
)


class CancellationRequest(BaseModel):
    executors: List[str]
    cancellation_context: Optional[dict[str, dict[str, str]]] = None

# Pydantic Web Models
class WebPipeline(BaseModel):
    short_name: str
    full_name: str
    description: str

class WebNode(BaseModel):
    name: str
    properties: Dict[str, Any] = {}
    additional_properties: Dict[str, Any] = {}
    architecture: str

class WebExperimentMapping(BaseModel):
    pipeline: WebPipeline
    nodes: List[WebNode]


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


@app.post("/api/v1/token")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Dict[str, str]:
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


@app.get("/api/v1/verify_token")
async def verify_token_handler(
    _: Annotated[str, Depends(verify_token)],
) -> Response:
    return Response(status_code=200)


@app.get("/api/v1/health")
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

@app.get("/api/v1/pipelines", status_code=200)
async def pipelines_handler() -> List[Dict[str, str]]:
    try:
        pipelines = get_pipelines()
        return pipelines
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

@app.post("/api/v1/web/experiment/prepare")
async def web_experiment_handler(
    web_experiment: WebExperimentMapping,
    username: Annotated[str, Depends(verify_token)],
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None
) -> Any: 
    
    netunicorn_auth_context_parsed = await parse_context(netunicorn_auth_context)
    pipeline_path = web_experiment.pipeline.full_name

    try:
        pipeline_module_name, pipeline_name = pipeline_path.rsplit('.', 1)
        pipeline_module = importlib.import_module(pipeline_module_name)
        get_selected_pipeline = getattr(pipeline_module, pipeline_name)
        selected_pipeline = get_selected_pipeline()
    except (ImportError, AttributeError) as e:
        raise HTTPException(status_code=400, detail=f"Error importing pipeline: {e}") #BAD EXPERIMENT
    
    selected_nodes = []
    for node in web_experiment.nodes:
        dict_node = node.model_dump(mode="json")
        selected_node = Node.from_json(dict_node)
        selected_nodes.append(selected_node)

    experiment_name = f"{pipeline_name}_experiment"
    web_experiment = Experiment().map(selected_pipeline, selected_nodes)

    prechecks = await asyncio.gather(
        experiment_precheck(web_experiment),
        check_sudo_access(web_experiment, username),
        check_runtime_context(web_experiment),
        check_environments(web_experiment),
    )

    for result in prechecks:
        if not is_successful(result):
            return result_to_response(result)
    
    try:
        await delete_experiment(experiment_name, username)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")
        
    try:
        await prepare_experiment_task(
            experiment_name,
            web_experiment,
            username,
            netunicorn_auth_context_parsed,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Preparation failed: {e}")
    
    try:
        while True:
            status_result = await get_experiment_status(experiment_name, username)
            if is_successful(status_result):
                status = status_result.unwrap().status
                logger.info("Preparing Poll: Experiment %s status: %s", experiment_name, status)
                if status == ExperimentStatus.READY: 
                    logger.info(f"Experiment '{experiment_name}' is ready.")
                    break
            else:
                logger.warning("Failed to fetch status for experiment %s during polling.", experiment_name)
            await asyncio.sleep(5)

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Polling failed: {e}")
        
    try:
        exec_result = await start_experiment(
            experiment_name,
            username,
            execution_context=None,
            netunicorn_authentication_context=netunicorn_auth_context_parsed,
        )
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")

    try:
        while True:
            status_result = await get_experiment_status(experiment_name, username)
            if is_successful(status_result):
                status = status_result.unwrap().status
                logger.info("Running Poll: Experiment %s status: %s", experiment_name, status)
                if status != ExperimentStatus.RUNNING: 
                    break
            else:
                logger.warning("Failed to fetch status for experiment %s during polling.", experiment_name)
            await asyncio.sleep(5)

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Polling failed: {e}")
    
    execution_graph_results = list(map(lambda exec_result: DeploymentExecutionResult.from_json(exec_result).result, status_result.unwrap().execution_result))
    unwrapped_execution_graph_results = []
    for result, log in execution_graph_results:
        if isinstance(result, Result):
            if is_successful(result):
                unwrapped_result = result.unwrap()
                for task_id in unwrapped_result:
                    unwrapped_result[task_id] = list(map(lambda task_element_result: task_element_result.unwrap(), unwrapped_result[task_id]))
                last_task_id = list(unwrapped_result.keys())[-1]
                last_task_results = {last_task_id: unwrapped_result[last_task_id]}
                logger.info("Last Task Results: %s", last_task_results)
                unwrapped_execution_graph_results.append(unwrapped_result)
            else:
                logger.info("Failure: %s", result.failure())
                raise HTTPException(status_code=500, detail=str(result.failure()))


    logger.info("Execution graph results: %s", unwrapped_execution_graph_results)
    return last_task_results, unwrapped_execution_graph_results

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


@app.get("/api/v1/ui/locks", status_code=200)
async def locked_nodes_handler(
    username: Annotated[str, Depends(verify_token)],
) -> Response:
    result = await get_locked_nodes(username)
    return result_to_response(result)


@app.get("/api/v1/ui/compilations", status_code=200)
async def active_compilations_handler(
    username: Annotated[str, Depends(verify_token)],
) -> Response:
    result = await get_active_compilations(username)
    return result_to_response(result)


@app.get("/api/v1/ui/running_experiments", status_code=200)
async def running_experiments_handler(
    username: Annotated[str, Depends(verify_token)],
) -> Response:
    result = await get_running_experiments(username)
    return result_to_response(result)


@app.get("/api/v1/ui/last_experiments", status_code=200)
async def last_experiments_handler(
    username: Annotated[str, Depends(verify_token)],
    days: int = 14,
) -> Response:
    result = await get_last_experiments(username, days)
    return result_to_response(result)


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
