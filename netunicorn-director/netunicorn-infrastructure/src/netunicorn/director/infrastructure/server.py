import json
from typing import Annotated, Any, Optional

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import Response
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.types import (
    ConnectorContext,
    ExecutorsCancellationRequest,
)

from .kernel import (
    deploy,
    execute,
    get_nodes,
    health,
    initialize,
    parse_config,
    shutdown,
    stop_execution,
    stop_executors,
)

app = FastAPI()
config: dict[str, Any]


async def parse_context(json_str: Optional[str]) -> ConnectorContext:
    if not json_str or json_str == "null":
        return None
    try:
        return json.loads(json_str)  # type: ignore
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't parse the context: {e}",
        )


@app.get("/health")
async def health_handler() -> Response:
    code, result = await health()
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.on_event("startup")
async def startup_handler() -> None:
    await initialize(config)


@app.on_event("shutdown")
async def shutdown_handler() -> None:
    await shutdown()


@app.get("/nodes/{username}", status_code=200)
async def get_nodes_handler(
    username: str,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    parsed_netunicorn_auth_context = await parse_context(netunicorn_auth_context)
    code, result = await get_nodes(username, parsed_netunicorn_auth_context)
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/deployment/{username}/{experiment_id}", status_code=200)
async def deployment_handler(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    parsed_netunicorn_auth_context = await parse_context(netunicorn_auth_context)
    code, result = await deploy(
        username, experiment_id, background_tasks, parsed_netunicorn_auth_context
    )
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/execution/{username}/{experiment_id}")
async def execution_handler(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    execution_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    parsed_netunicorn_auth_context = await parse_context(netunicorn_auth_context)
    code, result = await execute(
        username,
        experiment_id,
        background_tasks,
        execution_context,
        parsed_netunicorn_auth_context,
    )
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.delete("/execution/{username}/{experiment_id}")
async def stop_execution_handler(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    cancellation_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    parsed_netunicorn_auth_context = await parse_context(netunicorn_auth_context)
    code, result = await stop_execution(
        username,
        experiment_id,
        background_tasks,
        cancellation_context,
        parsed_netunicorn_auth_context,
    )
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.delete("/executors/{username}")
async def stop_executors_handler(
    username: str,
    cancellation_request: ExecutorsCancellationRequest,
    background_tasks: BackgroundTasks,
    netunicorn_auth_context: Annotated[Optional[str], Header()] = None,
) -> Response:
    parsed_netunicorn_auth_context = await parse_context(netunicorn_auth_context)
    code, result = await stop_executors(
        username,
        cancellation_request["executors"],
        background_tasks,
        cancellation_request.get("cancellation_context", None),
        parsed_netunicorn_auth_context,
    )
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


def main(filepath: str) -> None:
    global config
    config = parse_config(filepath)
    uvicorn.run(
        app,
        host=config["netunicorn.infrastructure.host"],
        port=config["netunicorn.infrastructure.port"],
        log_level=config["netunicorn.infrastructure.log.level"],
    )
