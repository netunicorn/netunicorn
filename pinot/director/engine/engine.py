import asyncio
import functools
from typing import Union, Optional, Dict, Tuple

from cloudpickle import dumps, loads

from pinot.base import Pipeline
from pinot.base.minions import MinionPool, Minion
from pinot.base.deployment_map import DeploymentMap, DeploymentStatus, DeploymentExecutionResult
from pinot.director.engine.resources import redis_connection, logger
from pinot.director.engine.config import deployer_connector
from pinot.director.engine.compiler import compile_environment
from pinot.director.engine.preprocessors import deployment_preprocessors


async def get_minion_pool(credentials: (str, str)) -> MinionPool:
    # TODO: check credentials and modify minion pool depending on user permissions
    return await deployer_connector.get_minion_pool()


async def compile_pipeline(credentials: (str, str), environment_id: str, pipeline: Pipeline) -> str:
    login, password = credentials

    # if environment is already being compiled, return environment_id
    result = await redis_connection.exists(f"{login}:pipeline:{environment_id}")
    if result:
        return environment_id
    # TODO: check credentials and hosts in the pipeline (if user has access to them)

    # start environment compilation background task (it would set DeploymentMap or Exception to redis when it's done)
    await redis_connection.set(f"{login}:pipeline:{environment_id}", dumps(None))
    asyncio.create_task(compile_environment(login, environment_id, pipeline))
    return environment_id


async def get_compiled_pipeline(credentials: (str, str), environment_id: str) -> Union[Pipeline, Exception, None]:
    login, password = credentials
    return loads(await redis_connection.get(f"{login}:pipeline:{environment_id}"))


async def deploy_map(credentials: (str, str), deployment_map: DeploymentMap, deployment_id: str) -> str:
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
    await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(DeploymentStatus.STARTING))
    (
        # when deploy_map finish it would start deployment_watcher(credentials, deployment_id, deploy_map_result)
        asyncio.create_task(deployer_connector.deploy_map(login, deployment_map, deployment_id))
            .add_done_callback(functools.partial(deployment_watcher, credentials, deployment_id))
    )
    return deployment_id


async def get_deployment_status(credentials: (str, str), deployment_id: str) -> DeploymentStatus:
    login, password = credentials
    result: Optional[DeploymentStatus] = loads(await redis_connection.get(f"{login}:deployment:{deployment_id}:status"))
    if result is None:
        return DeploymentStatus.UNKNOWN
    return result


async def get_deployment_result(
        credentials: (str, str),
        deployment_id: str
) -> Tuple[DeploymentStatus, Union[Dict[str, DeploymentExecutionResult], Exception]]:
    login, password = credentials
    status = loads(await redis_connection.get(f"{login}:deployment:{deployment_id}:status"))
    if status is None or status == DeploymentStatus.UNKNOWN:
        return DeploymentStatus.UNKNOWN, Exception(f"Deployment {deployment_id} is not found.")
    elif status == DeploymentStatus.STARTING:
        return status, {}
    elif status in {DeploymentStatus.RUNNING, DeploymentStatus.FINISHED}:
        result = loads(await redis_connection.get(f"{login}:deployment:{deployment_id}:result"))
        return status, result
    else:
        logger.error(f"Unknown deployment status <{status}> for deployment <{deployment_id}>")
        return DeploymentStatus.UNKNOWN, Exception(f"Unknown deployment status <{status}> for deployment <{deployment_id}>")


async def deployment_watcher(credentials: (str, str), deployment_id: str, executors: Dict[str, Minion]) -> None:
    """
    This function monitors deployment status, collect results
    """

    login, password = credentials
    await redis_connection.set(f"{login}:deployment:{deployment_id}:result", dumps({}))
    while True:
        status = loads(await redis_connection.get(f"{login}:deployment:{deployment_id}:status"))
        if status in {None, DeploymentStatus.UNKNOWN, DeploymentStatus.STARTING}:
            await redis_connection.set(
                f"{login}:deployment:{deployment_id}:result",
                dumps(Exception(f"Deployment {deployment_id} is in unexpected status <{status}>. "
                          f"See administrative logs for details."))
            )
            break

        # finishing condition - all executors reported results OR died
        # TODO: implement keep-alive for executors!
        if all(await redis_connection.exists(f"executor:{executor_id}:result") for executor_id in executors):
            status = DeploymentStatus.FINISHED
            await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(status))

        deployment_result = loads(await redis_connection.get(f"{login}:deployment:{deployment_id}:result")) or {}
        for (executor_id, minion) in executors.values():
            if not await redis_connection.exists(f"executor:{executor_id}:result"):
                continue
            result = loads(await redis_connection.get(f"executor:{executor_id}:result"))
            deployment_result[executor_id] = DeploymentExecutionResult(minion=minion, result=result)
        await redis_connection.set(f"{login}:deployment:{deployment_id}:result", dumps(deployment_result))

        if status == DeploymentStatus.FINISHED:
            # clean up
            for executor_id in executors:
                await redis_connection.delete(f"executor:{executor_id}:result")
                await redis_connection.delete(f"executor:{executor_id}:pipeline")
            await redis_connection.delete(f"{login}:deployment:{deployment_id}")
            break

        await asyncio.sleep(10)
    pass
