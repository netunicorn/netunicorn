import asyncio
import requests as req
from uuid import uuid4
from typing import Union, Optional, Dict, Tuple, List
from pickle import dumps, loads

from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.minions import MinionPool, Minion
from netunicorn.base.experiment import Experiment, ExperimentStatus, ExperimentExecutionResult, Deployment, SerializedExperimentExecutionResult
from netunicorn.director.base.resources import redis_connection
from .preprocessors import experiment_preprocessors
from .resources import logger, \
    NETUNICORN_COMPILATION_IP, NETUNICORN_COMPILATION_PORT, \
    NETUNICORN_INFRASTRUCTURE_IP, NETUNICORN_INFRASTRUCTURE_PORT, \
    NETUNICORN_PROCESSOR_IP, NETUNICORN_PROCESSOR_PORT


async def find_experiment_id_and_status_by_name(experiment_name: str, username: str) -> (str, ExperimentStatus):
    experiment_id = await redis_connection.get(f"{username}:experiment:name:{experiment_name}")
    if experiment_id is None:
        raise Exception(f"Experiment {experiment_name} not found")
    status_data = await redis_connection.get(f"experiment:{experiment_id}:status")
    if status_data is None:
        raise Exception(f"Experiment {experiment_name} status is unknown")
    status: ExperimentStatus = loads(status_data)
    return experiment_id, status


async def get_minion_pool(username: str) -> MinionPool:
    url = f"http://{NETUNICORN_INFRASTRUCTURE_IP}:{NETUNICORN_INFRASTRUCTURE_PORT}/minions"

    result = req.get(url, timeout=30)
    result.raise_for_status()
    return loads(result.content)


async def prepare_experiment_task(experiment_name: str, experiment: Experiment, username: str) -> None:
    async def prepare_deployment(deployment: Deployment) -> None:
        deployment.executor_id = str(uuid4())
        key = (deployment.environment_definition, deployment.pipeline, deployment.minion.get_architecture())
        if key not in envs:
            envs[key] = str(uuid4())
            url = f"http://{NETUNICORN_COMPILATION_IP}:{NETUNICORN_COMPILATION_PORT}/compile/"
            if isinstance(deployment.environment_definition, DockerImage):
                url += "docker"
                data = {
                    "uid": envs[key],
                    "architecture": deployment.minion.get_architecture(),
                    "environment_definition": dumps(deployment.environment_definition),
                    "pipeline": deployment.pipeline,
                }
                try:
                    req.post(url, data=data, timeout=30).raise_for_status()
                except Exception as e:
                    logger.exception(e)
                    await redis_connection.set(f"experiment:compilation:{envs[key]}", dumps((False, str(e))))
            elif isinstance(deployment.environment_definition, ShellExecution):
                # no preparation needed, commands would be executed during deployment stage
                await redis_connection.set(f"experiment:compilation:{envs[key]}", dumps((True, "")))
            else:
                await redis_connection.set(f"experiment:compilation:{envs[key]}", dumps((False, f"Unknown environment definition type: {deployment.environment_definition}")))

        if isinstance(deployment.environment_definition, DockerImage):
            deployment.environment_definition.image = f"{envs[key]}:latest"
        elif isinstance(deployment.environment_definition, ShellExecution):
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

    compilation_ids = list(envs.values())
    await redis_connection.set(f"experiment:{experiment_id}", dumps(experiment))
    await redis_connection.set(f"experiment:{experiment_id}:executors", dumps([d.executor_id for d in experiment]))
    await redis_connection.set(f"experiment:{experiment_id}:compilations", dumps(compilation_ids))

    try:
        url = f"http://{NETUNICORN_PROCESSOR_IP}:{NETUNICORN_PROCESSOR_PORT}/deploy/{experiment_id}"
        req.post(url, timeout=30).raise_for_status()
    except Exception as e:
        logger.exception(e)
        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
        await redis_connection.set(f"experiment:{experiment_id}:result", dumps(
            f"Error occurred during deployment, ask administrator for details. \n{e}"
        ))
        return


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



async def deployment_watcher(credentials: (str, str), deployment_id: str, executors: Dict[str, Minion]) -> None:
    """
    This function monitors deployment status, collect results
    """

    raise NotImplementedError()
    if not executors:
        logger.error(f"Executor list is empty! Deployment <{deployment_id}> is not started.")

    login, password = credentials
    await redis_connection.set(f"{login}:deployment:{deployment_id}:result", dumps({}))
    while True:
        status = await redis_connection.get(f"{login}:deployment:{deployment_id}:status")
        status = loads(status) if status else ExperimentStatus.UNKNOWN
        if status in {None, ExperimentStatus.UNKNOWN, ExperimentStatus.PREPARING}:
            await redis_connection.set(
                f"{login}:deployment:{deployment_id}:result",
                dumps(Exception(f"Deployment {deployment_id} is in unexpected status <{status}>. "
                                f"See administrative logs for details."))
            )
            break

        # finishing condition - all executors reported results OR died
        # TODO: implement keep-alive for executors!
        exs = await redis_connection.exists(*(f"executor:{executor_id}:result" for executor_id in executors))
        if exs >= len(executors):  # TODO: not all, but only initially ready to execute
            status = ExperimentStatus.FINISHED
            await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(status))

        deployment_result = await redis_connection.get(f"{login}:deployment:{deployment_id}:result")
        deployment_result = (loads(deployment_result) if deployment_result else {}) or {}
        for (executor_id, (minion, pipeline)) in executors.items():
            if not await redis_connection.exists(f"executor:{executor_id}:result"):
                continue
            result = await redis_connection.get(f"executor:{executor_id}:result")
            result = loads(result) if result else None
            deployment_result[executor_id] = ExperimentExecutionResult(minion=minion, result=result, pipeline=pipeline)
        await redis_connection.set(f"{login}:deployment:{deployment_id}:result", dumps(deployment_result))

        if status == ExperimentStatus.FINISHED:
            # clean up
            for executor_id in executors:
                await redis_connection.delete(f"executor:{executor_id}:result")
                await redis_connection.delete(f"executor:{executor_id}:pipeline")
            await redis_connection.delete(f"{login}:deployment:{deployment_id}")
            break

        await asyncio.sleep(10)
    pass
