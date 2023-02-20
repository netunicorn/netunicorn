import asyncio
import re
import subprocess
from collections.abc import Iterable
from typing import NoReturn, Optional

import asyncpg
import netunicorn.base.environment_definitions as environment_definitions
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)
from netunicorn.director.base.utils import __init_connection

logger = get_logger("netunicorn.director.compiler")


async def record_compilation_result(
    experiment_id: str,
    compilation_id: str,
    success: bool,
    log: str,
    db_conn_pool: asyncpg.Pool,
) -> None:
    await db_conn_pool.execute(
        "UPDATE compilations SET status = $3, result = $4 WHERE experiment_id = $1 AND compilation_id = $2",
        experiment_id,
        compilation_id,
        success,
        log,
    )


async def docker_compilation_cycle(
    db_pool: asyncpg.pool.Pool,
) -> bool:
    compilation_request = await db_pool.fetchrow(
        "SELECT "
        "experiment_id, compilation_id, architecture, "
        "pipeline::bytea, environment_definition::jsonb "
        "FROM compilations WHERE status IS NULL LIMIT 1"
    )
    if compilation_request is None:
        # nothing to compile, sleep
        return False

    experiment_id: str = compilation_request["experiment_id"]
    compilation_id: str = compilation_request["compilation_id"]
    architecture: str = compilation_request["architecture"]
    pipeline: Optional[bytes] = compilation_request["pipeline"]
    environment_definition = environment_definitions.DockerImage.from_json(
        compilation_request["environment_definition"]
    )

    if environment_definition.image is None:
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Container image name is not provided",
            db_pool,
        )
        return True

    if architecture not in {"linux/arm64", "linux/amd64"}:
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Unknown architecture for docker container: {architecture}",
            db_pool,
        )
        return True

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
            db_pool,
        )
        return True
    python_version = ".".join(match_result[0].split(".")[:2])

    commands = environment_definition.commands or []
    if not isinstance(commands, Iterable):
        await record_compilation_result(
            experiment_id,
            compilation_id,
            False,
            f"Commands list of the environment definition is incorrect. "
            f"Received object: {commands}",
            db_pool,
        )
        return True

    filelines = [
        f"FROM python:{python_version}-slim",
        "ENV DEBIAN_FRONTEND=noninteractive",
        "RUN apt update",
        *["RUN " + str(x).removeprefix("sudo ") for x in commands],
    ]

    if pipeline is not None:
        filelines.append(f"COPY {compilation_id}.pipeline unicorn.pipeline")
        with open(f"{compilation_id}.pipeline", "wb") as f:
            f.write(pipeline)

    filelines += [
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
        await record_compilation_result(
            experiment_id, compilation_id, False, log, db_pool
        )
        return True

    logger.debug(f"Finished compilation of {compilation_id}")
    if isinstance(result, subprocess.CompletedProcess):
        logger.debug(f"Return code: {result.returncode}")
    await record_compilation_result(
        experiment_id,
        compilation_id,
        True,
        result.stdout.decode("utf-8") + "\n" + result.stderr.decode("utf-8"),
        db_pool,
    )
    return True


async def main() -> NoReturn:
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        host=DATABASE_ENDPOINT,
        init=__init_connection,
    )
    await db_conn_pool.fetchval("SELECT 1")
    while True:
        result = await docker_compilation_cycle(db_conn_pool)
        if result:
            # something was compiled
            continue

        # nothing was compiled, wait for a while
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
