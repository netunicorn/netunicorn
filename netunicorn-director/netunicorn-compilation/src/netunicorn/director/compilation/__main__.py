import pickle
import subprocess
import re
import uvicorn

from collections.abc import Iterable
from base64 import b64decode

from fastapi import FastAPI, BackgroundTasks

from netunicorn.base.environment_definitions import EnvironmentDefinition, DockerImage
from netunicorn.director.base.resources import get_logger, redis_connection

from .api_types import CompilationRequest

logger = get_logger('netunicorn.director.compiler')

app = FastAPI()


@app.get('/health')
async def health_check() -> str:
    await redis_connection.ping()
    return 'OK'


@app.on_event("startup")
async def startup():
    await redis_connection.ping()


@app.on_event("shutdown")
async def shutdown():
    await redis_connection.close()


@app.post("/compile/shell")
async def shell_compilation(request: CompilationRequest):
    await record_compilation_result(request.uid, True, 'Shell environments do not require compilation.')


@app.post("/compile/docker")
async def docker_compilation(request: CompilationRequest, background_tasks: BackgroundTasks):
    environment_definition: EnvironmentDefinition = pickle.loads(b64decode(request.environment_definition))
    if not isinstance(environment_definition, DockerImage):
        raise ValueError(f'Environment definition is not an instance of DockerImage')

    background_tasks.add_task(docker_compilation_task, request.uid, request.architecture, environment_definition,
                              b64decode(request.pipeline))
    return {"result": "success"}


async def docker_compilation_task(uid: str, architecture: str, environment_definition: DockerImage,
                                  pipeline: bytes) -> None:
    if environment_definition.image is None:
        await record_compilation_result(uid, False, f'Container image name is not provided')
        return

    if architecture not in {'linux/arm64', 'linux/amd64'}:
        await record_compilation_result(uid, False, f"Unknown architecture for docker container: {architecture}")
        return

    match_result = re.fullmatch(r'\d\.\d+\.\d+', environment_definition.python_version)
    if not match_result:
        await record_compilation_result(uid, False, f'Unknown Python version: {environment_definition.python_version}')
        return
    python_version = '.'.join(match_result[0].split('.')[:2])

    commands = environment_definition.commands or []
    if not isinstance(commands, Iterable):
        await record_compilation_result(
            uid, False,
            f"Commands list of the environment definition is incorrect. "
            f"Received object: {commands}"
        )
        return

    with open(f'{uid}.pipeline', 'wb') as f:
        f.write(pipeline)

    filelines = [
        f'FROM python:{python_version}-slim',
        "ENV DEBIAN_FRONTEND=noninteractive",
        "RUN apt update",
        *['RUN ' + str(x).removeprefix('sudo ') for x in commands],
        f'COPY {uid}.pipeline unicorn.pipeline',

        # TODO: change for milestone 0.2 to PYPI
        f'COPY netunicorn-base netunicorn-base',
        f'RUN pip install netunicorn-base/',
        f'COPY netunicorn-executor netunicorn-executor',
        f'RUN pip install netunicorn-executor/',

        f'CMD ["python", "-m", "netunicorn.executor"]',
    ]

    filelines = [x + '\n' for x in filelines]

    with open(f'{uid}.Dockerfile', 'wt') as f:
        f.writelines(filelines)

    result = None
    try:
        result = subprocess.run([
            'docker', 'buildx', 'build',
            '--platform', architecture,
            '-t', f'{environment_definition.image}',
            '-f', f'{uid}.Dockerfile',
            '--push',
            '.',
        ], capture_output=True)
        result.check_returncode()
    except Exception as e:
        log = f'{e}'
        if result is not None:
            log += f'\n{result.stdout.decode()}'
            log += f'\n{result.stderr.decode()}'
        await record_compilation_result(uid, False, log)
        return

    logger.debug(f'Finished compilation of {uid}')
    if isinstance(result, subprocess.CompletedProcess):
        logger.debug(f"Return code: {result.returncode}")
    await record_compilation_result(uid, True, result.stdout.decode('utf-8') + '\n' + result.stderr.decode('utf-8'))


async def record_compilation_result(uid: str, success: bool, log: str) -> None:
    result = pickle.dumps((success, log))
    await redis_connection.set(f"experiment:compilation:{uid}", result)
    return


uvicorn.run(app, host="127.0.0.1", port=26513)
