import asyncio
import base64

import requests as req
from uuid import uuid4
from typing import Union, Optional, Dict, Tuple
from pickle import dumps, loads

from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.experiment import Experiment, ExperimentStatus, Deployment, \
    SerializedExperimentExecutionResult
from netunicorn.director.base.resources import redis_connection
from .preprocessors import experiment_preprocessors
from .resources import logger, \
    NETUNICORN_COMPILATION_IP, NETUNICORN_COMPILATION_PORT, \
    NETUNICORN_INFRASTRUCTURE_IP, NETUNICORN_INFRASTRUCTURE_PORT, \
    NETUNICORN_PROCESSOR_IP, NETUNICORN_PROCESSOR_PORT, \
    DOCKER_REGISTRY_URL


async def find_experiment_id_and_status_by_name(experiment_name: str, username: str) -> (str, ExperimentStatus):
    experiment_id = await redis_connection.get(f"{username}:experiment:name:{experiment_name}")
    if experiment_id is None:
        raise Exception(f"Experiment {experiment_name} not found")
    status_data = await redis_connection.get(f"experiment:{experiment_id}:status")
    if status_data is None:
        raise Exception(f"Experiment {experiment_name} status is unknown")
    status: ExperimentStatus = loads(status_data)
    return experiment_id, status


async def get_minion_pool(username: str) -> bytes:
    url = f"http://{NETUNICORN_INFRASTRUCTURE_IP}:{NETUNICORN_INFRASTRUCTURE_PORT}/minions"

    result = req.get(url, timeout=30)
    result.raise_for_status()
    return result.content


async def prepare_experiment_task(experiment_name: str, experiment: Experiment, username: str) -> None:
    async def prepare_deployment(deployment: Deployment) -> None:
        deployment.executor_id = str(uuid4())
        key = hash((deployment.environment_definition, deployment.pipeline, deployment.minion.get_architecture()))
        if key not in envs:
            compilation_uid = str(uuid4())
            envs[key] = compilation_uid
            url = f"http://{NETUNICORN_COMPILATION_IP}:{NETUNICORN_COMPILATION_PORT}/compile/"

            if isinstance(deployment.environment_definition, DockerImage) and deployment.environment_definition.image is not None:
                await redis_connection.set(f"experiment:compilation:{compilation_uid}", dumps((True, "Docker image provided explicitly")))
            elif isinstance(deployment.environment_definition, DockerImage) and deployment.environment_definition.image is None:
                url += "docker"
                data = {
                    "uid": compilation_uid,
                    "architecture": deployment.minion.get_architecture(),
                    "environment_definition": base64.b64encode(dumps(deployment.environment_definition)).decode('utf-8'),
                    "pipeline": base64.b64encode(deployment.pipeline).decode("utf-8"),
                }
                try:
                    result = req.post(url, json=data, timeout=30)
                    if result.status_code != 200:
                        raise Exception(f"Compilation failed: {result.content}")
                except Exception as e:
                    logger.exception(e)
                    await redis_connection.set(f"experiment:compilation:{compilation_uid}", dumps((False, str(e))))
            elif isinstance(deployment.environment_definition, ShellExecution):
                # no preparation needed, commands would be executed during deployment stage
                await redis_connection.set(f"experiment:compilation:{compilation_uid}", dumps((True, "")))
            else:
                await redis_connection.set(f"experiment:compilation:{compilation_uid}", dumps(
                    (False, f"Unknown environment definition type: {deployment.environment_definition}")))
        else:
            compilation_uid = envs[key]

        if isinstance(deployment.environment_definition, DockerImage) and deployment.environment_definition.image is None:
            deployment.environment_definition.image = deployment.environment_definition.image or f"{DOCKER_REGISTRY_URL}/{envs[key]}:latest"
            key = hash((deployment.environment_definition, deployment.pipeline, deployment.minion.get_architecture()))
            envs[key] = compilation_uid

        if isinstance(deployment.environment_definition, ShellExecution):
            await redis_connection.set(f"executor:{deployment.executor_id}:pipeline", deployment.pipeline)

    # if experiment is already in progress - do nothing
    if await redis_connection.exists(f"{username}:experiment:name:{experiment_name}"):
        return

    experiment_id = str(uuid4())
    await redis_connection.set(f"{username}:experiment:name:{experiment_name}", experiment_id)
    await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.PREPARING))

    try:
        # apply all defined preprocessors
        for p in experiment_preprocessors:
            experiment = p(experiment)
    except Exception as e:
        logger.exception(e)
        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
        await redis_connection.set(f"experiment:{experiment_id}:result", dumps(
            f"Error occurred during applying preprocessors, ask administrator for details. \n{e}"
        ))
        return

    # get all distinct combinations of environment_definitions and pipelines, and add compilation_request info to experiment items
    envs = {}
    for deployment in experiment:
        await prepare_deployment(deployment)

    compilation_ids = set(envs.values())
    await redis_connection.set(f"experiment:{experiment_id}", dumps(experiment))
    await redis_connection.set(f"experiment:{experiment_id}:executors", dumps([d.executor_id for d in experiment]))
    await redis_connection.set(f"experiment:{experiment_id}:compilations", dumps(compilation_ids))

    everything_compiled = False
    while not everything_compiled:
        await asyncio.sleep(5)
        logger.debug(f"Waiting for compilation of {compilation_ids}")
        compilation_flags = await asyncio.gather(*[
            redis_connection.exists(f"experiment:compilation:{compilation_id}")
            for compilation_id in compilation_ids
        ])
        everything_compiled = all(compilation_flags)

    # collect compilation results and set preparation flag for all minions
    compilation_results: Dict[str, Tuple[bool, str]] = {
        compilation_id: loads(await redis_connection.get(f"experiment:compilation:{compilation_id}"))
        for compilation_id in compilation_ids
    }

    for deployment in experiment:
        key = hash((deployment.environment_definition, deployment.pipeline, deployment.minion.get_architecture()))
        compilation_result = compilation_results[envs[key]]
        deployment.prepared = compilation_result[0]
        if not compilation_result[0]:
            deployment.error = Exception(compilation_result[1])

    await redis_connection.set(f"experiment:{experiment_id}", dumps(experiment))

    # start deployment of environments
    try:
        url = f"http://{NETUNICORN_INFRASTRUCTURE_IP}:{NETUNICORN_INFRASTRUCTURE_PORT}/start_deployment/{experiment_id}"
        req.post(url, timeout=30).raise_for_status()
    except Exception as e:
        logger.exception(e)
        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
        await redis_connection.set(f"experiment:{experiment_id}:result", dumps(
            f"Error occurred during deployment, ask administrator for details. \n{e}"
        ))


async def get_experiment_status(experiment_name: str, username: str) -> Tuple[
    ExperimentStatus,
    Optional[Experiment],
    Union[
        None,
        Exception,
        Dict[str, SerializedExperimentExecutionResult],
    ]
]:
    experiment_id, status = await find_experiment_id_and_status_by_name(experiment_name, username)
    experiment = await redis_connection.get(f"experiment:{experiment_id}")
    result = await redis_connection.get(f"experiment:{experiment_id}:result")
    return status, experiment, result


async def start_experiment(experiment_name: str, username: str) -> None:
    experiment_id, status = await find_experiment_id_and_status_by_name(experiment_name, username)
    if status != ExperimentStatus.READY:
        raise Exception(f"Experiment {experiment_name} is not ready to start. Current status: {status}")

    url = f"http://{NETUNICORN_INFRASTRUCTURE_IP}:{NETUNICORN_INFRASTRUCTURE_PORT}/start_execution/{experiment_id}"
    req.post(url, timeout=30).raise_for_status()

    url = f"http://{NETUNICORN_PROCESSOR_IP}:{NETUNICORN_PROCESSOR_PORT}/watch_experiment/{experiment_id}"
    req.post(url, timeout=30).raise_for_status()
