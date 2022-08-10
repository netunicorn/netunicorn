import asyncio
from typing import Union, Optional, Dict, Tuple

from cloudpickle import dumps, loads

from pinot.base.minions import MinionPool, Minion
from pinot.base.experiment import Experiment, ExperimentStatus, ExperimentExecutionResult
from pinot.director.engine.resources import redis_connection, logger
from pinot.director.engine.config import deployer_connector
from pinot.director.engine.compiler import compile_deployment
from pinot.director.engine.preprocessors import deployment_preprocessors


async def get_minion_pool(credentials: (str, str)) -> MinionPool:
    # TODO: check credentials and modify minion pool depending on user permissions
    return await deployer_connector.get_minion_pool()


async def prepare_deployment(credentials: (str, str), deployment_map: Experiment, deployment_id: str) -> str:
    login, password = credentials

    # if deployment is already in progress - return deployment_id
    result = await redis_connection.exists(f"{login}:deployment:{deployment_id}")
    if result:
        return deployment_id

    # apply all defined preprocessors
    for p in deployment_preprocessors:
        deployment_map = p(deployment_map)

    # else: set deployment_id to redis and start background process
    await redis_connection.set(f"{login}:deployment:{deployment_id}", dumps(None))
    await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(ExperimentStatus.PREPARING))
    asyncio.create_task(compile_and_call_prepare(credentials, deployment_map, deployment_id))
    return deployment_id


async def start_execution(credentials: (str, str), deployment_id: str) -> Union[Exception, str]:
    login, password = credentials
    content = await redis_connection.get(f"{login}:deployment:{deployment_id}:status")
    result: Optional[ExperimentStatus] = loads(content) if content else None
    if result != ExperimentStatus.READY:
        exception = Exception(f"Deployment {deployment_id} is in status {result}. Cannot proceed (yet).")
        logger.exception(exception)
        raise exception

    deployment_map = await redis_connection.get(f"{login}:deployment:{deployment_id}")
    deployment_map = loads(deployment_map) if deployment_map else None
    if not deployment_map:
        exception = Exception(f"Deployment {deployment_id} is not prepared. Cannot proceed.")
        logger.exception(exception)
        raise exception
    asyncio.create_task(deploy_and_start_watcher(credentials, deployment_map, deployment_id))
    return deployment_id


async def compile_and_call_prepare(credentials: (str, str), deployment_map: Experiment, deployment_id: str) -> None:
    login, password = credentials
    for deployment in deployment_map:
        await compile_deployment(credentials, deployment_id, deployment)

    try:
        await deployer_connector.prepare_deployment(credentials, deployment_map, deployment_id)
        await redis_connection.set(f"{login}:deployment:{deployment_id}", dumps(deployment_map))
        await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(ExperimentStatus.READY))
    except Exception as e:
        logger.exception(e)
        await redis_connection.set(f"{login}:deployment:{deployment_id}", dumps(deployment_map))
        await redis_connection.set(f"{login}:deployment:{deployment_id}:result", dumps(e))
        await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(ExperimentStatus.FINISHED))


async def deploy_and_start_watcher(credentials: (str, str), deployment_map: Experiment, deployment_id: str) -> None:
    login, password = credentials
    result = await deployer_connector.start_execution(login, deployment_map, deployment_id)
    await deployment_watcher(credentials, deployment_id, result)


async def get_deployment_status(
        credentials: (str, str), deployment_id: str
) -> Tuple[ExperimentStatus, Optional[Experiment]]:
    login, password = credentials
    content = await redis_connection.get(f"{login}:deployment:{deployment_id}:status")
    result: Optional[ExperimentStatus] = loads(content) if content else None
    if result is None:
        return ExperimentStatus.UNKNOWN, None
    if result == ExperimentStatus.FINISHED:
        return result, None

    content = await redis_connection.get(f"{login}:deployment:{deployment_id}")
    deployment_map: Optional[Experiment] = loads(content) if content else None
    if deployment_map is None:
        return ExperimentStatus.UNKNOWN, None
    return result, deployment_map


async def get_deployment_result(
        credentials: (str, str),
        deployment_id: str
) -> Tuple[ExperimentStatus, Union[Dict[str, ExperimentExecutionResult], Exception]]:
    login, password = credentials
    status = await redis_connection.get(f"{login}:deployment:{deployment_id}:status")
    status = loads(status) if status else ExperimentStatus.UNKNOWN
    if status is None or status == ExperimentStatus.UNKNOWN:
        return ExperimentStatus.UNKNOWN, Exception(f"Deployment {deployment_id} is not found.")
    elif status == ExperimentStatus.PREPARING:
        return status, {}
    elif status in {ExperimentStatus.RUNNING, ExperimentStatus.FINISHED, ExperimentStatus.READY}:
        content = await redis_connection.get(f"{login}:deployment:{deployment_id}:result")
        result = loads(content) if content else None
        return status, result
    else:
        logger.error(f"Unknown deployment status <{status}> for deployment <{deployment_id}>")
        return ExperimentStatus.UNKNOWN, Exception(
            f"Unknown deployment status <{status}> for deployment <{deployment_id}>")


async def deployment_watcher(credentials: (str, str), deployment_id: str, executors: Dict[str, Minion]) -> None:
    """
    This function monitors deployment status, collect results
    """
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
