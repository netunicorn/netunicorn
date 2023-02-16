import json
from typing import List, Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import Response
from netunicorn.base.utils import UnicornEncoder

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
async def get_nodes_handler(username: str) -> Response:
    code, result = await get_nodes(username)
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/deployment/{username}/{experiment_id}", status_code=200)
async def deployment_handler(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Response:
    code, result = await deploy(username, experiment_id, background_tasks)
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.post("/execution/{username}/{experiment_id}")
async def execution_handler(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Response:
    code, result = await execute(username, experiment_id, background_tasks)
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.delete("/execution/{username}/{experiment_id}")
async def stop_execution_handler(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Response:
    code, result = await stop_execution(username, experiment_id, background_tasks)
    return Response(
        status_code=code,
        content=json.dumps(result, cls=UnicornEncoder),
        media_type="application/json",
    )


@app.delete("/executors/{username}")
async def stop_executors_handler(
    username: str, executors: List[str], background_tasks: BackgroundTasks
) -> Response:
    code, result = await stop_executors(username, executors, background_tasks)
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
