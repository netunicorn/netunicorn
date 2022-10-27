import re
import subprocess
from base64 import b64decode
from collections.abc import Iterable
from typing import Optional

import asyncpg
import netunicorn.base.environment_definitions as environment_definitions
import uvicorn
from fastapi import BackgroundTasks, FastAPI
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)

from .api_types import CompilationRequest

logger = get_logger("netunicorn.director.compiler")

app = FastAPI()
db_conn_pool: Optional[asyncpg.Pool] = None


@app.get("/health")
async def health_check() -> str:
    await db_conn_pool.fetchval("SELECT 1")
    return "OK"


@app.on_event("startup")
async def startup():
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        host=DATABASE_ENDPOINT,
    )
    await db_conn_pool.fetchval("SELECT 1")


@app.on_event("shutdown")
async def shutdown():
    await db_conn_pool.close()


@app.post("/compile/shell")
async def shell_compilation(request: CompilationRequest):
    await record_compilation_result(
        request.experiment_id,
        request.compilation_id,
        True,
        "Shell environments do not require compilation.",
    )


@app.post("/compile/docker")
async def docker_compilation(
    request: CompilationRequest, background_tasks: BackgroundTasks
):
    environment_definition = environment_definitions.DockerImage.from_json(
        request.environment_definition
    )
    background_tasks.add_task(
        docker_compilation_task,
        request.experiment_id,
        request.compilation_id,
        request.architecture,
        environment_definition,
        b64decode(request.pipeline),
    )
    return {"result": "success"}


async def docker_compilation_task(
    experiment_id: str,
    compilation_id: str,
    architecture: str,
    environment_definition: environment_definitions.DockerImage,
    pipeline: bytes,
) -> None:
    if environment_definition.image is None:
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Container image name is not provided",
        )
        return

    if architecture not in {"linux/arm64", "linux/amd64"}:
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Unknown architecture for docker container: {architecture}",
        )
        return

    logger.debug(
        f"Received compilation request: {compilation_id=}, {architecture=}, "
        f"{environment_definition=}, {environment_definition.build_context=}"
    )
    match_result = re.fullmatch(
        r"\d\.\d+\.\d+", environment_definition.build_context.python_version
    )
    if not match_result:
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Unknown Python version: {environment_definition.build_context.python_version}",
        )
        return
    python_version = ".".join(match_result[0].split(".")[:2])

    commands = environment_definition.commands or []
    if not isinstance(commands, Iterable):
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Commands list of the environment definition is incorrect. "
            f"Received object: {commands}",
        )
        return

    with open(f"{compilation_id}.pipeline", "wb") as f:
        f.write(pipeline)

    filelines = [
        f"FROM python:{python_version}-slim",
        "ENV DEBIAN_FRONTEND=noninteractive",
        "RUN apt update",
        *["RUN " + str(x).removeprefix("sudo ") for x in commands],
        f"COPY {compilation_id}.pipeline unicorn.pipeline",
        f"RUN pip install netunicorn-base",
        f"RUN pip install netunicorn-executor",
    ]

    if environment_definition.build_context.cloudpickle_version is not None:
        filelines.append(
            f"RUN pip install cloudpickle=={environment_definition.build_context.cloudpickle_version}"
        )

    filelines.append(f'CMD ["python", "-m", "netunicorn.executor"]')

    filelines = [x + "\n" for x in filelines]

    with open(f"{compilation_id}.Dockerfile", "wt") as f:
        f.writelines(filelines)

    result = None
    try:
        result = subprocess.run(
            [
                "docker",
                "buildx",
                "build",
                "--platform",
                architecture,
                "-t",
                f"{environment_definition.image}",
                "-f",
                f"{compilation_id}.Dockerfile",
                "--push",
                ".",
            ],
            capture_output=True,
        )
        result.check_returncode()
    except Exception as e:
        log = f"{e}"
        if result is not None:
            log += f"\n{result.stdout.decode()}"
            log += f"\n{result.stderr.decode()}"
        await record_compilation_result(experiment_id, compilation_id, False, log)
        return

    logger.debug(f"Finished compilation of {compilation_id}")
    if isinstance(result, subprocess.CompletedProcess):
        logger.debug(f"Return code: {result.returncode}")
    await record_compilation_result(
        experiment_id,
        compilation_id,
        True,
        result.stdout.decode("utf-8") + "\n" + result.stderr.decode("utf-8"),
    )


async def record_compilation_result(
    experiment_id: str, compilation_id: str, success: bool, log: str
) -> None:
    await db_conn_pool.execute(
        "INSERT INTO compilations (experiment_id, compilation_id, status, result) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (experiment_id, compilation_id) DO UPDATE SET status = $3, result = $4",
        experiment_id,
        compilation_id,
        success,
        log,
    )
    return


uvicorn.run(app, host="127.0.0.1", port=26513)
