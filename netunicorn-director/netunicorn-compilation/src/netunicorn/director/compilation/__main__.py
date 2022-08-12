import os
import pickle
import subprocess
import re
from collections.abc import Iterable
from base64 import b64decode

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uvicorn

from netunicorn.base.environment_definitions import EnvironmentDefinition, DockerImage

app = FastAPI()
docker_registry_url = os.environ.get('NETUNICORN_DOCKER_REGISTRY_URL', 'pinot.cs.ucsb.edu')  # TODO: change for milestone 0.2


class CompilationRequest(BaseModel):
    uid: str
    architecture: str
    environment_definition: bytes
    pipeline: bytes


@app.post("/compile/shell")
async def shell_compilation(request: CompilationRequest):
    raise NotImplementedError()


@app.post("/compile/docker")
async def docker_compilation(request: CompilationRequest, background_tasks: BackgroundTasks):
    environment_definition: EnvironmentDefinition = pickle.loads(b64decode(request.environment_definition))
    if not isinstance(environment_definition, DockerImage):
        raise ValueError(f'Environment definition is not an instance of DockerImage')

    background_tasks.add_task(docker_compilation_task, request.uid, request.architecture, environment_definition, b64decode(request.pipeline))
    return {"result": "success"}


def docker_compilation_task(uid: str, architecture: str, environment_definition: DockerImage, pipeline: bytes) -> None:
    if environment_definition.image is not None:
        record_compilation_result(uid, True, f'Image {environment_definition.image} is provided explicitly.')
        return

    if architecture not in {'linux/arm64', 'linux/amd64'}:
        record_compilation_result(uid, False, f"Unknown architecture for docker container: {architecture}")
        return

    match_result = re.fullmatch(r'\d\.\d+\.\d+', environment_definition.python_version)
    if not match_result:
        record_compilation_result(uid, False, f'Unknown Python version: {environment_definition.python_version}')
        return
    python_version = '.'.join(match_result[0].split('.')[:2])

    commands = environment_definition.commands or []
    if not isinstance(commands, Iterable):
        record_compilation_result(
            uid, False,
            f"Commands list of the environment definition is incorrect. "
            f"Received object: {commands}"
        )
        return

    with open(f'{uid}.pipeline', 'wb') as f:
        f.write(pipeline)

    filelines = [
        f'FROM python:{python_version}',
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
            '-t', f'{docker_registry_url}:{uid}',
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
        record_compilation_result(uid, False, log)
        return

    record_compilation_result(uid, True, result.stdout.decode('utf-8') + '\n' + result.stderr.decode('utf-8'))


def record_compilation_result(uid: str, success: bool, log: str) -> None:
    print(f'{uid}: {success}')
    print(log)
    return


uvicorn.run(app, host="0.0.0.0", port=26521)
