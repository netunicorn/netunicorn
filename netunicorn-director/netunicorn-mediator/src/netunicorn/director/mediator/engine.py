import asyncio
import base64
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import asyncpg.connection
import requests as req
from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.experiment import (
    Deployment,
    Experiment,
    ExperimentExecutionInformation,
    ExperimentStatus,
)
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
)
from netunicorn.director.base.utils import __init_connection
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from .preprocessors import experiment_preprocessors
from .resources import (
    DOCKER_REGISTRY_URL,
    NETUNICORN_AUTH_ENDPOINT,
    NETUNICORN_COMPILATION_ENDPOINT,
    NETUNICORN_INFRASTRUCTURE_ENDPOINT,
    NETUNICORN_PROCESSOR_ENDPOINT,
    logger,
)

db_conn_pool: Optional[asyncpg.Pool] = None
current_tasks = set()


async def open_db_connection() -> None:
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        host=DATABASE_ENDPOINT,
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        init=__init_connection,
    )


async def close_db_connection() -> None:
    await db_conn_pool.close()


async def check_services_availability():
    await db_conn_pool.fetchval("SELECT 1")

    for url in [
        NETUNICORN_INFRASTRUCTURE_ENDPOINT,
        NETUNICORN_PROCESSOR_ENDPOINT,
        NETUNICORN_COMPILATION_ENDPOINT,
        NETUNICORN_AUTH_ENDPOINT,
    ]:
        req.get(f"{url}/health", timeout=30).raise_for_status()


async def get_experiment_id_and_status(
    experiment_name: str, username: str
) -> Result[Tuple[str, ExperimentStatus], str]:
    data = await db_conn_pool.fetchrow(
        "SELECT experiment_id, status FROM experiments WHERE username = $1 AND experiment_name = $2",
        username,
        experiment_name,
    )
    if data is None:
        return Failure(f"Experiment {experiment_name} not found")
    experiment_id, status_data = data["experiment_id"], data["status"]
    try:
        status: ExperimentStatus = ExperimentStatus(status_data)
    except ValueError:
        logger.warn(f"Invalid experiment status: {status_data}")
        status = ExperimentStatus.UNKNOWN
    return Success((experiment_id, status))


async def get_minion_pool(username: str) -> list:
    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/minions"
    result = req.get(url, timeout=300)
    result.raise_for_status()
    serialized_minion_pool = result.json()
    result = []
    for minion in serialized_minion_pool:
        minion_name = minion.get("name", "")
        current_lock = await db_conn_pool.fetchval(
            "SELECT username FROM locks WHERE minion_name = $1", minion_name
        )
        if current_lock is None or current_lock == username:
            result.append(minion)
        else:
            logger.debug(f"Minion {minion_name} is locked by {current_lock}")
    return result


async def check_sudo_access(experiment: Experiment, username: str) -> Result[None, str]:
    """
    checking additional_arguments in runtime_context of environment definitions and whether user us allowed to use them
    """
    sudo_user = await db_conn_pool.fetchval(
        "SELECT sudo FROM authentication WHERE username = $1", username
    )
    if not sudo_user:
        for executor in experiment.deployment_map:
            if isinstance(executor.environment_definition, DockerImage) or isinstance(
                executor.environment_definition, ShellExecution
            ):
                if executor.environment_definition.runtime_context.additional_arguments:
                    return Failure(
                        f"This user is not allowed to use additional arguments in runtime context"
                    )
    return Success(None)


async def check_runtime_context(experiment: Experiment) -> Result[None, str]:
    def check_ports_types(ports_mapping: dict) -> bool:
        for k, v in ports_mapping.items():
            try:
                int(k), int(v)
            except ValueError:
                return False
        return True

    def check_env_values(env_mapping: dict) -> bool:
        for k, v in env_mapping.items():
            if " " in k or " " in v:
                return False
        return True

    for executor in experiment.deployment_map:
        if isinstance(executor.environment_definition, DockerImage):
            if not check_ports_types(
                executor.environment_definition.runtime_context.ports_mapping
            ):
                return Failure(
                    f"Ports mapping in runtime context must be a dict of int to int"
                )
            if not check_env_values(
                executor.environment_definition.runtime_context.environment_variables
            ):
                return Failure(
                    f"Environment variables in runtime context must not contain spaces"
                )
        elif isinstance(executor.environment_definition, ShellExecution):
            if not check_env_values(
                executor.environment_definition.runtime_context.environment_variables
            ):
                return Failure(
                    f"Environment variables in runtime context must not contain spaces"
                )
    return Success(None)


async def experiment_precheck(experiment: Experiment) -> Result[None, str]:
    # checking executor names
    executor_names = set()
    for executor in experiment.deployment_map:
        if executor.executor_id != "":
            if executor.executor_id in executor_names:
                return Failure(
                    f"Experiment has non-unique non-empty executor id: {executor.executor_id}"
                )
            executor_names.add(executor.executor_id)
    return Success(None)


async def prepare_experiment_task(
    experiment_name: str, experiment: Experiment, username: str
) -> None:
    async def prepare_deployment(_username: str, _deployment: Deployment) -> None:
        _deployment.executor_id = str(uuid4())
        env_def = _deployment.environment_definition

        # insert minion name if it doesn't exist yet
        await db_conn_pool.execute(
            "INSERT INTO locks (minion_name) VALUES ($1) ON CONFLICT DO NOTHING",
            _deployment.minion.name,
        )

        # check and set lock on device for the user
        current_lock = await db_conn_pool.fetchval(
            "UPDATE locks SET username = $1 WHERE minion_name = $2 AND (username IS NULL OR username = $1) RETURNING username",
            _username,
            _deployment.minion.name,
        )
        if current_lock != _username:
            _deployment.prepared = False
            _deployment.error = Exception(
                f"Minion {_deployment.minion.name} is already locked by {current_lock}"
            )
            return

        if isinstance(env_def, ShellExecution):
            # nothing to do with shell execution
            await db_conn_pool.execute(
                "INSERT INTO executors (experiment_id, executor_id, pipeline, minion_name, finished) VALUES ($1, $2, $3, $4, FALSE) ON CONFLICT DO NOTHING",
                experiment_id,
                _deployment.executor_id,
                _deployment.minion.name,
                _deployment.pipeline,
            )
            _deployment.prepared = True
            return

        if not isinstance(env_def, DockerImage):
            # unknown environment definition - just invalidate deployment and go on
            _deployment.prepared = False
            _deployment.error = Exception(
                f"Unknown environment definition type: {_deployment.environment_definition}"
            )
            return

        if (
            isinstance(env_def, DockerImage)
            and _deployment.environment_definition.image is not None
        ):
            # specific case: if key is in the envs, that means that we need to wait this deployment too
            # description: that happens when 2 deployments have the same environment definition object in memory,
            #  so update of image name for one deployment will affect another deployment
            _key = hash(
                (_deployment.pipeline, env_def, _deployment.minion.architecture)
            )
            if _key in envs:
                deployments_waiting_for_compilation.append(_deployment)
                return

            # if docker image is provided - just provide pipeline
            await db_conn_pool.execute(
                "INSERT INTO executors (experiment_id, executor_id, minion_name, pipeline, finished) VALUES ($1, $2, $3, $4, FALSE) ON CONFLICT DO NOTHING",
                experiment_id,
                _deployment.executor_id,
                _deployment.minion.name,
                _deployment.pipeline,
            )
            _deployment.prepared = True
            return

        if (
            isinstance(env_def, DockerImage)
            and _deployment.environment_definition.image is None
        ):
            deployments_waiting_for_compilation.append(_deployment)

            # unique compilation is combination of pipeline, docker commands, and minion architecture
            _key = hash(
                (_deployment.pipeline, env_def, _deployment.minion.architecture)
            )
            if _key in envs:
                # we already started this compilation
                env_def.image = f"{DOCKER_REGISTRY_URL}/{envs[_key]}:latest"
                return

            # if not - we create a new compilation request
            compilation_uid = str(uuid4())
            _deployment.environment_definition.image = (
                f"{DOCKER_REGISTRY_URL}/{compilation_uid}:latest"
            )

            # put compilation_uid both to:
            #  - original key without image name (so any similar deployments will find it)
            #  - key with image name (so we can find it later)
            envs[_key] = compilation_uid
            envs[
                hash((_deployment.pipeline, env_def, _deployment.minion.architecture))
            ] = compilation_uid

            # start compilation process for this compilation request
            _url = f"{NETUNICORN_COMPILATION_ENDPOINT}/compile/docker"
            _data = {
                "experiment_id": experiment_id,
                "compilation_id": compilation_uid,
                "architecture": _deployment.minion.architecture.value,
                "environment_definition": _deployment.environment_definition.__json__(),
                "pipeline": base64.b64encode(_deployment.pipeline).decode("utf-8"),
            }
            try:
                req.post(_url, json=_data, timeout=30).raise_for_status()
            except Exception as _e:
                logger.exception(_e)
                await db_conn_pool.execute(
                    "INSERT INTO compilations (experiment_id, compilation_id, status, result) VALUES ($1, $2, $3, $4) "
                    "ON CONFLICT (experiment_id, compilation_id) DO UPDATE SET status = $3, result = $4",
                    experiment_id,
                    compilation_uid,
                    False,
                    str(_e),
                )

    # if experiment is already in progress - do nothing
    if await db_conn_pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM experiments WHERE username = $1 AND experiment_name = $2)",
        username,
        experiment_name,
    ):
        return

    experiment_id = str(uuid4())
    await db_conn_pool.execute(
        "INSERT INTO experiments (username, experiment_name, experiment_id, status, creation_time) VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
        username,
        experiment_name,
        experiment_id,
        ExperimentStatus.PREPARING.value,
        datetime.utcnow(),
    )

    try:
        # apply all defined preprocessors
        for p in experiment_preprocessors:
            experiment = p(experiment)
    except Exception as e:
        logger.exception(e)
        user_error = "Error occurred during applying preprocessors, ask administrator for details. \n{e}"
        await db_conn_pool.execute(
            "UPDATE experiments SET status = $1, error = $2 WHERE experiment_id = $3",
            ExperimentStatus.FINISHED.value,
            user_error,
            experiment_id,
        )
        return

    # get all distinct combinations of environment_definitions and pipelines, and add compilation_request info to experiment items
    envs = {}  # key: unique compilation request, result: compilation_uid
    deployments_waiting_for_compilation = []
    for deployment in experiment:
        await prepare_deployment(username, deployment)

    compilation_ids = set(envs.values())
    await db_conn_pool.execute(
        "UPDATE experiments SET data = $1::jsonb WHERE experiment_id = $2",
        experiment,
        experiment_id,
    )
    await db_conn_pool.executemany(
        "INSERT INTO compilations (experiment_id, compilation_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        [(experiment_id, compilation_id) for compilation_id in compilation_ids],
    )
    await db_conn_pool.executemany(
        "INSERT INTO executors (experiment_id, executor_id, minion_name, finished) VALUES ($1, $2, $3, FALSE) ON CONFLICT DO NOTHING",
        [(experiment_id, d.executor_id, d.minion.name) for d in experiment],
    )

    everything_compiled = False
    while not everything_compiled:
        await asyncio.sleep(5)
        logger.debug(f"Waiting for compilation of {compilation_ids}")
        compilation_statuses = await db_conn_pool.fetch(
            "SELECT status IS NOT NULL AS result FROM compilations WHERE experiment_id = $1 AND compilation_id = ANY($2)",
            experiment_id,
            list(compilation_ids),
        )
        everything_compiled = all([c["result"] for c in compilation_statuses])

    # collect compilation results and set preparation flag for all minions
    compilation_results: Dict[str, Tuple[bool, str]] = {}
    data = await db_conn_pool.fetch(
        "SELECT compilation_id, status, result FROM compilations WHERE experiment_id = $1 AND compilation_id = ANY($2)",
        experiment_id,
        list(compilation_ids),
    )
    for result in data:
        compilation_results[result["compilation_id"]] = (
            result["status"],
            result["result"],
        )

    # set Not found flags for all not found in the table
    successful_compilation_ids = {result["compilation_id"] for result in data}
    not_found_compilation_ids = compilation_ids - successful_compilation_ids
    for compilation_id in not_found_compilation_ids:
        compilation_results[compilation_id] = (False, "Compilation result not found")

    for deployment in deployments_waiting_for_compilation:
        key = hash(
            (
                deployment.pipeline,
                deployment.environment_definition,
                deployment.minion.architecture,
            )
        )
        compilation_result = compilation_results.get(
            envs.get(key, None), (False, "Compilation result not found")
        )
        deployment.prepared = compilation_result[0]
        if not compilation_result[0]:
            deployment.error = Exception(compilation_result[1])

    await db_conn_pool.execute(
        "UPDATE experiments SET data = $1::jsonb WHERE experiment_id = $2",
        experiment,
        experiment_id,
    )

    # start deployment of environments
    try:
        url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/start_deployment/{experiment_id}"
        req.post(url, timeout=30).raise_for_status()
    except Exception as e:
        logger.exception(e)
        error = (
            f"Error occurred during deployment, ask administrator for details. \n{e}"
        )
        await db_conn_pool.execute(
            "UPDATE experiments SET status = $1, error = $2 WHERE experiment_id = $3",
            ExperimentStatus.FINISHED.value,
            error,
            experiment_id,
        )


async def get_experiment_status(
    experiment_name: str, username: str
) -> Result[ExperimentExecutionInformation, str]:
    result = await get_experiment_id_and_status(experiment_name, username)
    if not is_successful(result):
        return Failure(result.failure())
    experiment_id, status = result.unwrap()

    row = await db_conn_pool.fetchrow(
        "SELECT data::jsonb, error, execution_results::jsonb[] FROM experiments WHERE experiment_id = $1",
        experiment_id,
    )
    if row is None:
        return Failure(f"Experiment {experiment_name} of user {username} was not found")
    experiment, error, execution_results = (
        row["data"],
        row["error"],
        row["execution_results"],
    )
    if experiment is not None:
        experiment = Experiment.from_json(experiment)
    if error is not None:
        return Success(ExperimentExecutionInformation(status, experiment, error))
    return Success(
        ExperimentExecutionInformation(status, experiment, execution_results)
    )


async def start_experiment(experiment_name: str, username: str) -> Result[str, str]:
    result = await get_experiment_id_and_status(experiment_name, username)
    if not is_successful(result):
        return Failure(result.failure())
    experiment_id, status = result.unwrap()

    if status != ExperimentStatus.READY:
        return Failure(
            f"Experiment {experiment_name} is not ready to start. Current status: {status}"
        )

    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/start_execution/{experiment_id}"
    req.post(url, timeout=30).raise_for_status()

    url = f"{NETUNICORN_PROCESSOR_ENDPOINT}/watch_experiment/{experiment_id}/{username}"
    req.post(url, timeout=30).raise_for_status()
    return Success(experiment_name)


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


async def cancel_experiment(experiment_name: str, username: str) -> Result[str, str]:
    result = await get_experiment_id_and_status(experiment_name, username)
    if not is_successful(result):
        return Failure(result.failure())
    experiment_id, status = result.unwrap()

    executors = await db_conn_pool.fetch(
        "SELECT executor_id FROM executors WHERE experiment_id = $1 AND finished = FALSE",
        experiment_id,
    )
    await cancel_executors_task([x["executor_id"] for x in executors])
    return Success(f"Experiment {experiment_name} cancellation started")


async def cancel_executors(executors: List[str], username: str) -> Result[str, str]:
    # check data format
    for executor in executors:
        if not isinstance(executor, str):
            return Failure(f"Invalid executor name: {executor}, type: {type(executor)}")

    # get all usernames of executors
    usernames = await db_conn_pool.fetch(
        "SELECT username, executor_id FROM experiments "
        "JOIN executors ON experiments.experiment_id = executors.experiment_id "
        "WHERE executor_id = ANY($1::text[]) "
        "AND finished = FALSE",
        executors,
    )
    usernames = {x["executor_id"]: x["username"] for x in usernames}

    if not usernames:
        return Failure(
            f"All executors already finished or no experiments found belonging to user {username} with given executors: {executors}"
        )

    if set(usernames.values()) != {username}:
        other_executors = [x for x in executors if usernames[x] != username]
        return Failure(
            f"Some of executors do not belong to user {username}: \n {other_executors}"
        )

    await cancel_executors_task(executors)
    return Success("Executors cancellation started")


async def cancel_executors_task(executors: List[str]) -> None:
    url = f"{NETUNICORN_INFRASTRUCTURE_ENDPOINT}/cancel_executors"
    req.post(url, json=executors, timeout=30).raise_for_status()
