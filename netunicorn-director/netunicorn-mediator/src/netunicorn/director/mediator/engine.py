import asyncio
import base64
import json

import asyncpg.connection
import requests as req
from uuid import uuid4
from typing import Union, Optional, Dict, Tuple, List
from datetime import datetime

from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.utils import UnicornEncoder
from netunicorn.base.experiment import Experiment, ExperimentStatus, Deployment, SerializedExperimentExecutionResult
from netunicorn.director.base.resources import DATABASE_ENDPOINT, DATABASE_USER, DATABASE_PASSWORD, DATABASE_DB

from .preprocessors import experiment_preprocessors
from .resources import logger, \
    NETUNICORN_COMPILATION_ENDPOINT, NETUNICORN_INFRASTRUCTURE_ENDPOINT, \
    NETUNICORN_PROCESSOR_ENDPOINT, DOCKER_REGISTRY_URL, NETUNICORN_AUTH_ENDPOINT

db_connection: Optional[asyncpg.connection.Connection] = None


async def open_db_connection() -> None:
    global db_connection
    db_connection = await asyncpg.connect(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
    )

    await db_connection.set_type_codec(
        'json',
        encoder=lambda x: json.dumps(x, cls=UnicornEncoder),
        decoder=json.loads,
        schema='pg_catalog'
    )


async def close_db_connection() -> None:
    await db_connection.close()


async def check_services_availability():
    await db_connection.fetchval('SELECT 1')

    for url in [
        NETUNICORN_INFRASTRUCTURE_ENDPOINT,
        NETUNICORN_PROCESSOR_ENDPOINT,
        NETUNICORN_COMPILATION_ENDPOINT,
        NETUNICORN_AUTH_ENDPOINT,
    ]:
        req.get(f"{url}/health", timeout=30).raise_for_status()


async def get_experiment_id_and_status(experiment_name: str, username: str) -> (str, ExperimentStatus):
    experiment_id, status_data = await db_connection.fetchval(
        "SELECT experiment_id, status FROM experiments WHERE username = $1 AND experiment_name = $2",
        username, experiment_name
    )
    if experiment_id is None:
        raise Exception(f"Experiment {experiment_name} not found")
    try:
        status: ExperimentStatus = ExperimentStatus(status_data)
    except ValueError:
        logger.warn(f"Invalid experiment status: {status_data}")
        status = ExperimentStatus.UNKNOWN
    return experiment_id, status


async def get_minion_pool(username: str) -> list:
    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/minions"
    result = req.get(url, timeout=300)
    result.raise_for_status()
    serialized_minion_pool = result.json()
    result = []
    for minion in serialized_minion_pool:
        minion_name = minion.get("name", "")
        current_lock = await db_connection.fetchval(
            "SELECT username FROM locks WHERE minion_name = $1",
            minion_name
        )
        if current_lock is None or current_lock == username:
            result.append(minion)
    return result


async def prepare_experiment_task(experiment_name: str, experiment: Experiment, username: str) -> None:
    async def prepare_deployment(_username: str, _deployment: Deployment) -> None:
        _deployment.executor_id = str(uuid4())
        env_def = _deployment.environment_definition

        # insert minion name if it doesn't exist yet
        await db_connection.execute(
            "INSERT INTO locks (minion_name) VALUES ($1) ON CONFLICT DO NOTHING",
            _deployment.minion.name
        )

        # check and set lock on device for the user
        current_lock = await db_connection.fetchval(
            "UPDATE locks SET username = $1 WHERE minion_name = $2 AND (username IS NULL OR username = $1) RETURNING username",
            _username, _deployment.minion.name
        )
        if current_lock != _username:
            _deployment.prepared = False
            _deployment.error = Exception(f"Minion {_deployment.minion.name} is already locked by {current_lock}")
            return

        if isinstance(env_def, ShellExecution):
            # nothing to do with shell execution
            await db_connection.execute(
                "INSERT INTO executors (experiment_id, executor_id, pipeline, finished) VALUES ($1, $2, $3, FALSE) ON CONFLICT DO NOTHING",
                experiment_id, _deployment.executor_id, _deployment.pipeline
            )
            _deployment.prepared = True
            return

        if not isinstance(env_def, DockerImage):
            # unknown environment definition - just invalidate deployment and go on
            _deployment.prepared = False
            _deployment.error = Exception(f"Unknown environment definition type: {_deployment.environment_definition}")
            return

        if isinstance(env_def, DockerImage) and _deployment.environment_definition.image is not None:
            # specific case: if key is in the envs, that means that we need to wait this deployment too
            # description: that happens when 2 deployments have the same environment definition object in memory,
            #  so update of image name for one deployment will affect another deployment
            _key = hash((_deployment.pipeline, env_def, _deployment.minion.architecture))
            if _key in envs:
                deployments_waiting_for_compilation.append(_deployment)
                return

            # if docker image is provided - just provide pipeline
            await db_connection.execute(
                "INSERT INTO executors (experiment_id, executor_id, pipeline, finished) VALUES ($1, $2, $3, FALSE) ON CONFLICT DO NOTHING",
                experiment_id, _deployment.executor_id, _deployment.pipeline
            )
            _deployment.prepared = True
            return

        if isinstance(env_def, DockerImage) and _deployment.environment_definition.image is None:
            deployments_waiting_for_compilation.append(_deployment)

            # unique compilation is combination of pipeline, docker commands, and minion architecture
            _key = hash((_deployment.pipeline, env_def, _deployment.minion.architecture))
            if _key in envs:
                # we already started this compilation
                env_def.image = f"{DOCKER_REGISTRY_URL}/{envs[_key]}:latest"
                return

            # if not - we create a new compilation request
            compilation_uid = str(uuid4())
            _deployment.environment_definition.image = f"{DOCKER_REGISTRY_URL}/{compilation_uid}:latest"

            # put compilation_uid both to:
            #  - original key without image name (so any similar deployments will find it)
            #  - key with image name (so we can find it later)
            envs[_key] = compilation_uid
            envs[hash((_deployment.pipeline, env_def, _deployment.minion.architecture))] = compilation_uid

            # start compilation process for this compilation request
            _url = f"{NETUNICORN_COMPILATION_ENDPOINT}/compile/docker"
            data = {
                "experiment_id": experiment_id,
                "compilation_uid": compilation_uid,
                "architecture": _deployment.minion.architecture.value,
                "environment_definition": _deployment.environment_definition.__json__(),
                "pipeline": base64.b64encode(_deployment.pipeline).decode("utf-8"),
            }
            try:
                req.post(_url, json=data, timeout=30).raise_for_status()
            except Exception as _e:
                logger.exception(_e)
                await db_connection.execute(
                    "INSERT INTO compilations (experiment_id, compilation_id, status, result) VALUES ($1, $2, $3, $4) "
                    "ON CONFLICT (experiment_id, compilation_id) DO UPDATE SET status = $3, result = $4",
                    experiment_id, compilation_uid, False, str(_e)
                )

    # if experiment is already in progress - do nothing
    if await db_connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM experiments WHERE username = $1 AND experiment_name = $2)",
            username, experiment_name
    ):
        return

    experiment_id = str(uuid4())
    await db_connection.execute(
        "INSERT INTO experiments (username, experiment_name, experiment_id, status, creation_time) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
        username, experiment_name, experiment_id, ExperimentStatus.PREPARING.value, datetime.utcnow()
    )

    try:
        # apply all defined preprocessors
        for p in experiment_preprocessors:
            experiment = p(experiment)
    except Exception as e:
        logger.exception(e)
        user_error = "Error occurred during applying preprocessors, ask administrator for details. \n{e}"
        await db_connection.execute(
            "UPDATE experiments SET status = $1, error = $2 WHERE experiment_id = $3",
            ExperimentStatus.FINISHED.value, user_error, experiment_id
        )
        return

    # get all distinct combinations of environment_definitions and pipelines, and add compilation_request info to experiment items
    envs = {}  # key: unique compilation request, result: compilation_uid
    deployments_waiting_for_compilation = []
    for deployment in experiment:
        await prepare_deployment(username, deployment)

    compilation_ids = set(envs.values())
    await db_connection.execute(
        "UPDATE experiments SET data = $1::json WHERE experiment_id = $2",
        experiment, experiment_id
    )
    await db_connection.executemany(
        "INSERT INTO compilations (experiment_id, compilation_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        [(experiment_id, compilation_id) for compilation_id in compilation_ids]
    )
    await db_connection.executemany(
        "INSERT INTO executors (experiment_id, executor_id, finished) VALUES ($1, $2, FALSE) ON CONFLICT DO NOTHING",
        [(experiment_id, d.executor_id) for d in experiment]
    )

    everything_compiled = False
    while not everything_compiled:
        await asyncio.sleep(5)
        logger.debug(f"Waiting for compilation of {compilation_ids}")
        compilation_flags = await asyncio.gather(*[
            db_connection.fetchval(
                "SELECT status FROM compilations WHERE experiment_id = $1 AND compilation_id = $2",
                experiment_id, compilation_id
            )
            for compilation_id in compilation_ids
        ])
        everything_compiled = all(compilation_flags)

    # collect compilation results and set preparation flag for all minions
    compilation_results: Dict[str, Tuple[bool, str]] = {
        compilation_id: await db_connection.fetchval(
            "SELECT status, result FROM compilations WHERE experiment_id = $1 AND compilation_id = $2",
            experiment_id, compilation_id
        )
        for compilation_id in compilation_ids
    }

    for deployment in deployments_waiting_for_compilation:
        key = hash((deployment.pipeline, deployment.environment_definition, deployment.minion.architecture))
        compilation_result = compilation_results.get(envs.get(key, None), (False, "Compilation result not found"))
        deployment.prepared = compilation_result[0]
        if not compilation_result[0]:
            deployment.error = Exception(compilation_result[1])

    await db_connection.execute(
        "UPDATE experiments SET data = $1::json WHERE experiment_id = $2",
        experiment, experiment_id
    )

    # start deployment of environments
    try:
        url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/start_deployment/{experiment_id}"
        req.post(url, timeout=30).raise_for_status()
    except Exception as e:
        logger.exception(e)
        error = f"Error occurred during deployment, ask administrator for details. \n{e}"
        await db_connection.execute(
            "UPDATE experiments SET status = $1, error = $2 WHERE experiment_id = $3",
            ExperimentStatus.FINISHED.value, error, experiment_id
        )


async def get_experiment_status(experiment_name: str, username: str) -> Tuple[
    ExperimentStatus,
    Optional[Experiment],
    Union[
        None,
        Exception,
        List[SerializedExperimentExecutionResult],
    ]
]:
    experiment_id, status = await get_experiment_id_and_status(experiment_name, username)
    experiment, error, execution_results = await db_connection.fetchval(
        "SELECT data::json, error, execution_results::json FROM experiments WHERE experiment_id = $1",
        experiment_id
    )
    if experiment is not None:
        experiment = Experiment.from_json(experiment)
    if error is not None:
        return status, experiment, error
    return status, experiment, execution_results


async def start_experiment(experiment_name: str, username: str) -> None:
    experiment_id, status = await get_experiment_id_and_status(experiment_name, username)
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
