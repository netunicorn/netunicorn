import asyncio
import base64

import requests as req
from uuid import uuid4
from typing import Union, Optional, Dict, Tuple, List
from pickle import dumps, loads

from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.experiment import Experiment, ExperimentStatus, Deployment, \
    SerializedExperimentExecutionResult
from netunicorn.director.base.resources import redis_connection
from .preprocessors import experiment_preprocessors
from .resources import logger, \
    NETUNICORN_COMPILATION_ENDPOINT, NETUNICORN_INFRASTRUCTURE_ENDPOINT, \
    NETUNICORN_PROCESSOR_ENDPOINT, DOCKER_REGISTRY_URL, NETUNICORN_AUTH_ENDPOINT


async def check_services_availability():
    for url in [
        NETUNICORN_INFRASTRUCTURE_ENDPOINT,
        NETUNICORN_PROCESSOR_ENDPOINT,
        NETUNICORN_COMPILATION_ENDPOINT,
        NETUNICORN_AUTH_ENDPOINT,
    ]:
        req.get(f"{url}/health", timeout=30).raise_for_status()


async def find_experiment_id_and_status_by_name(experiment_name: str, username: str) -> (str, ExperimentStatus):
    experiment_id = await redis_connection.get(f"{username}:experiment:name:{experiment_name}")
    if experiment_id is None:
        raise Exception(f"Experiment {experiment_name} not found")
    if isinstance(experiment_id, bytes):
        experiment_id = experiment_id.decode('utf-8')
    status_data = await redis_connection.get(f"experiment:{experiment_id}:status")
    if status_data is None:
        raise Exception(f"Experiment {experiment_name} status is unknown")
    status: ExperimentStatus = loads(status_data)
    return experiment_id, status


async def get_minion_pool(username: str) -> list:
    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/minions"
    result = req.get(url, timeout=300)
    result.raise_for_status()
    serialized_minion_pool = result.json()
    result = []
    for minion in serialized_minion_pool:
        minion_name = minion.get("name", "")
        current_lock = await redis_connection.get(f"minion:{minion_name}:lock")
        if current_lock is None or current_lock == username:
            result.append(minion)
    return result


async def prepare_experiment_task(experiment_name: str, experiment: Experiment, username: str) -> None:
    async def prepare_deployment(username: str, deployment: Deployment) -> None:
        deployment.executor_id = str(uuid4())
        env_def = deployment.environment_definition

        # check and set lock on device for the user
        try_set_lock = await redis_connection.set(f"minion:{deployment.minion.name}:lock", username, nx=True)
        if not try_set_lock and (current_lock := await redis_connection.get(f"minion:{deployment.minion.name}:lock")) != username:
            deployment.prepared = False
            deployment.error = Exception(f"Minion {deployment.minion.name} is already locked by {current_lock}")
            return

        if isinstance(env_def, ShellExecution):
            # nothing to do with shell execution
            await redis_connection.set(f"executor:{deployment.executor_id}:pipeline", deployment.pipeline)
            deployment.prepared = True
            return

        if not isinstance(env_def, DockerImage):
            # unknown environment definition - just invalidate deployment and go on
            deployment.prepared = False
            deployment.error = Exception(f"Unknown environment definition type: {deployment.environment_definition}")
            return

        if isinstance(env_def, DockerImage) and deployment.environment_definition.image is not None:
            # specific case: if key is in the envs, that means that we need to wait this deployment too
            # description: that happens when 2 deployments have the same environment definition object in memory,
            #  so update of image name for one deployment will affect another deployment
            key = hash((deployment.pipeline, env_def, deployment.minion.architecture))
            if key in envs:
                deployments_waiting_for_compilation.append(deployment)
                return

            # if docker image is provided - just provide pipeline
            await redis_connection.set(f"executor:{deployment.executor_id}:pipeline", deployment.pipeline)
            deployment.prepared = True
            return

        if isinstance(env_def, DockerImage) and deployment.environment_definition.image is None:
            deployments_waiting_for_compilation.append(deployment)

            # unique compilation is combination of pipeline, docker commands, and minion architecture
            key = hash((deployment.pipeline, env_def, deployment.minion.architecture))
            if key in envs:
                # we already started this compilation
                env_def.image = f"{DOCKER_REGISTRY_URL}/{envs[key]}:latest"
                return

            # if not - we create a new compilation request
            compilation_uid = str(uuid4())
            deployment.environment_definition.image = f"{DOCKER_REGISTRY_URL}/{compilation_uid}:latest"

            # put compilation_uid both to:
            #  - original key without image name (so any similar deployments will find it)
            #  - key with image name (so we can find it later)
            envs[key] = compilation_uid
            envs[hash((deployment.pipeline, env_def, deployment.minion.architecture))] = compilation_uid

            # start compilation process for this compilation request
            url = f"{NETUNICORN_COMPILATION_ENDPOINT}/compile/docker"
            data = {
                "uid": compilation_uid,
                "architecture": deployment.minion.architecture.value,
                "environment_definition": base64.b64encode(dumps(deployment.environment_definition)).decode(
                    'utf-8'),
                "pipeline": base64.b64encode(deployment.pipeline).decode("utf-8"),
            }
            try:
                result = req.post(url, json=data, timeout=30)
                if result.status_code != 200:
                    raise Exception(f"Compilation failed: {result.content}")
            except Exception as e:
                logger.exception(e)
                await redis_connection.set(f"experiment:compilation:{compilation_uid}", dumps((False, str(e))))

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
            Exception(f"Error occurred during applying preprocessors, ask administrator for details. \n{e}")
        ))
        return

    # get all distinct combinations of environment_definitions and pipelines, and add compilation_request info to experiment items
    envs = {}  # key: unique compilation request, result: compilation_uid
    deployments_waiting_for_compilation = []
    for deployment in experiment:
        await prepare_deployment(username, deployment)

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
    # TODO: check that all types are valid because it's received from external source
    compilation_results: Dict[str, Tuple[bool, str]] = {
        compilation_id: loads(await redis_connection.get(f"experiment:compilation:{compilation_id}"))
        for compilation_id in compilation_ids
    }

    for deployment in deployments_waiting_for_compilation:
        key = hash((deployment.pipeline, deployment.environment_definition, deployment.minion.architecture))
        compilation_result = compilation_results.get(envs.get(key, None), (False, "Compilation result not found"))
        deployment.prepared = compilation_result[0]
        if not compilation_result[0]:
            deployment.error = Exception(compilation_result[1])

    await redis_connection.set(f"experiment:{experiment_id}", dumps(experiment))

    # start deployment of environments
    try:
        url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/start_deployment/{experiment_id}"
        req.post(url, timeout=30).raise_for_status()
    except Exception as e:
        logger.exception(e)
        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
        await redis_connection.set(f"experiment:{experiment_id}:result", dumps(
            Exception(f"Error occurred during deployment, ask administrator for details. \n{e}")
        ))


async def get_experiment_status(experiment_name: str, username: str) -> Tuple[
    ExperimentStatus,
    Optional[Experiment],
    Union[
        None,
        Exception,
        List[SerializedExperimentExecutionResult],
    ]
]:
    experiment_id, status = await find_experiment_id_and_status_by_name(experiment_name, username)
    experiment = await redis_connection.get(f"experiment:{experiment_id}")
    if experiment is not None:
        experiment = loads(experiment)
    result = await redis_connection.get(f"experiment:{experiment_id}:result")
    if result is not None:
        result = loads(result)
    return status, experiment, result


async def start_experiment(experiment_name: str, username: str) -> None:
    experiment_id, status = await find_experiment_id_and_status_by_name(experiment_name, username)
    if status != ExperimentStatus.READY:
        raise Exception(f"Experiment {experiment_name} is not ready to start. Current status: {status}")

    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/start_execution/{experiment_id}"
    req.post(url, timeout=30).raise_for_status()

    url = f"{NETUNICORN_PROCESSOR_ENDPOINT}/watch_experiment/{experiment_id}/{username}"
    req.post(url, timeout=30).raise_for_status()


async def credentials_check(username: str, token: str) -> bool:
    url = f"{NETUNICORN_AUTH_ENDPOINT}/auth"
    data = {
        "username": username,
        "token": token,
    }
    try:
        result = req.post(url, json=data, timeout=30)
        return result.status_code == 200
    except Exception as e:
        logger.exception(e)
        return False
