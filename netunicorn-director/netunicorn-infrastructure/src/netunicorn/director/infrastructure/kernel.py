from __future__ import annotations

import asyncio
import importlib
import os
from collections import defaultdict
from logging import Logger
from typing import Any, NoReturn, Optional, Tuple, Union

import asyncpg
import yaml
from asyncpg import Record
from fastapi import BackgroundTasks
from netunicorn.base.deployment import Deployment
from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.nodes import CountableNodePool, Nodes
from netunicorn.base.types import ExperimentRepresentation
from netunicorn.director.base.connectors.protocol import NetunicornConnectorProtocol
from netunicorn.director.base.connectors.types import StopExecutorRequest
from netunicorn.director.base.resources import LOGGING_LEVELS, get_logger
from netunicorn.director.base.types import ConnectorContext
from netunicorn.director.base.utils import __init_connection
from returns.result import Failure, Success

from .tasks import cleanup_watchdog_task

logger: Logger
db_connection_pool: asyncpg.pool.Pool
connectors: dict[str, NetunicornConnectorProtocol] = {}
tasks: dict[str, asyncio.Task[NoReturn]] = {}


async def initialize_connector(
    connector_name: str, config: dict[str, Any], default_gateway: str
) -> None:
    if "enabled" in config and not config["enabled"]:
        logger.info(f"Skipping connector {connector_name} as disabled")
        return

    config_file: str | None = config.get("config", None)
    netunicorn_gateway = config.get("netunicorn.gateway.endpoint", default_gateway)
    connector_module = config.get("module", None)
    if connector_module is None:
        raise ValueError(f"Connector module for {connector_name} is not specified")
    connector_class = config.get("class", None)
    if connector_class is None:
        raise ValueError(f"Connector class for {connector_name} is not specified")

    # try to instantiate the connector
    cls = getattr(importlib.import_module(connector_module), connector_class)
    try:
        connector_logger = get_logger(
            f"netunicorn.director.infrastructure.connectors.{connector_name}"
        )
        connector_logger.setLevel(logger.getEffectiveLevel())
        connector = cls(
            connector_name, config_file, netunicorn_gateway, connector_logger
        )
        await connector.initialize()
        connectors[connector_name] = connector
        logger.info(f"Connector {connector_name} initialized")
    except Exception as e:
        logger.exception(f"Failed to initialize connector {connector_name}: {e}")
    return


def parse_config(filepath: str) -> dict[str, Any]:
    """
    Parse configuration file
    All parameters are read from the next priority list:
    1. Environment variables (corresponds to the name of the parameter in uppercase and with underscores instead of dots)
    2. Configuration file
    3. Default values


    :param filepath: path to the configuration file
    :return: dictionary with the configuration parameters
    """

    global logger

    with open(filepath, "r") as f:
        config = yaml.safe_load(f)
        assert isinstance(config, dict)

    # log level
    config["netunicorn.infrastructure.log.level"] = (
        os.environ.get("NETUNICORN_INFRASTRUCTURE_LOG_LEVEL", None)
        or config.get("netunicorn.infrastructure.log.level", None)
        or os.environ.get("NETUNICORN_LOG_LEVEL", None)
        or "info"
    ).lower()
    logger_level = config["netunicorn.infrastructure.log.level"].upper()
    if logger_level not in LOGGING_LEVELS:
        raise ValueError(f"Invalid log level {logger_level}")
    logger = get_logger(
        "netunicorn.director.infrastructure", LOGGING_LEVELS[logger_level]
    )
    logger.info(f"Logger initialized, level: {logger_level}")

    # module host and port
    config["netunicorn.infrastructure.host"] = (
        os.environ.get("NETUNICORN_INFRASTRUCTURE_IP", False)
        or config.get("netunicorn.infrastructure.ip", False)
        or "0.0.0.0"
    )
    logger.info(f"Host: {config['netunicorn.infrastructure.host']}")
    config["netunicorn.infrastructure.port"] = (
        int(os.environ.get("NETUNICORN_INFRASTRUCTURE_PORT", False))
        or int(config.get("netunicorn.infrastructure.port", False))
        or 26514
    )
    logger.info(f"Port: {config['netunicorn.infrastructure.port']}")

    # module gateway
    # required, even if separately set for each connector (could be dummy)
    # just to prevent forgetting to set it
    config["netunicorn.gateway.endpoint"] = (
        os.environ.get("NETUNICORN_GATEWAY_ENDPOINT")
        or config["netunicorn.gateway.endpoint"]
    )  # required
    logger.info(f"Gateway endpoint: {config['netunicorn.gateway.endpoint']}")

    # netunicorn database
    config["netunicorn.database.endpoint"] = (
        os.environ.get("NETUNICORN_DATABASE_ENDPOINT", False)
        or config.get("netunicorn.database.endpoint", False)
        or "127.0.0.1"
    )
    config["netunicorn.database.user"] = (
        os.environ.get("NETUNICORN_DATABASE_USER", False)
        or config["netunicorn.database.user"]
    )
    config["netunicorn.database.password"] = (
        os.environ.get("NETUNICORN_DATABASE_PASSWORD", False)
        or config["netunicorn.database.password"]
    )
    config["netunicorn.database.db"] = (
        os.environ.get("NETUNICORN_DATABASE_DB", False)
        or config.get("netunicorn.database.db", False)
        or "unicorndb"
    )
    logger.info(
        f"Database: {config['netunicorn.database.db']}, user: {config['netunicorn.database.user']}, endpoint: {config['netunicorn.database.endpoint']}"
    )
    return config


async def initialize(config: dict[str, Any]) -> None:
    global db_connection_pool

    db_connection_pool = await asyncpg.create_pool(
        host=config["netunicorn.database.endpoint"],
        user=config["netunicorn.database.user"],
        password=config["netunicorn.database.password"],
        database=config["netunicorn.database.db"],
        init=__init_connection,
        min_size=1,
        max_size=5,
    )
    await db_connection_pool.fetchval("SELECT 1")

    connectors_config = config.get("netunicorn.infrastructure.connectors", {})
    if len(connectors_config) == 0:
        logger.warning("No connectors configured")

    for connector_name, connector_config in connectors_config.items():
        await initialize_connector(
            connector_name, connector_config, config["netunicorn.gateway.endpoint"]
        )

    tasks["cleanup"] = asyncio.create_task(
        cleanup_watchdog_task(
            connectors=connectors, db_conn_pool=db_connection_pool, logger=logger
        )
    )

    return


async def health() -> Tuple[int, str]:
    statuses: list[Tuple[str, bool, str]] = []
    try:
        await db_connection_pool.fetchval("SELECT 1")
        statuses.append(("database", True, "OK"))
    except Exception as e:
        statuses.append(("database", False, str(e)))

    for connector_name in set(connectors.keys()):
        connector = connectors[connector_name]
        try:
            status, description = await connector.health()
        except Exception as e:
            status, description = False, str(e)
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
        statuses.append((connector_name, status, description))

    global_status = 200 if all([status for _, status, _ in statuses]) else 500
    return global_status, "\n".join(
        [f"{name}: {status} - {description}" for name, status, description in statuses]
    )


async def shutdown() -> None:
    await db_connection_pool.close()
    for connector_name, connector in connectors.items():
        try:
            await connector.shutdown()
        except Exception as e:
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )


async def get_nodes(
    username: str,
    netunicorn_authentication_context: ConnectorContext = None,
) -> Tuple[int, Union[Nodes, str]]:
    pools = []
    for connector_name in set(connectors.keys()):
        connector = connectors[connector_name]
        try:
            connector_authentication_context = None
            if (
                netunicorn_authentication_context
                and connector_name in netunicorn_authentication_context
            ):
                connector_authentication_context = netunicorn_authentication_context[
                    connector_name
                ]
            nodes = await connector.get_nodes(
                username, connector_authentication_context
            )
            nodes.set_property("connector", connector_name)
            pools.append(nodes)
        except Exception as e:
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
    return 200, CountableNodePool(nodes=pools)  # type: ignore


async def deploy(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    netunicorn_authentication_context: ConnectorContext = None,
) -> Tuple[int, str]:
    # 1. take experiment information from the database
    experiment_data: ExperimentRepresentation = await db_connection_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
        experiment_id,
    )
    if experiment_data is None:
        return 404, f"Experiment {experiment_id} not found"

    experiment: Experiment = Experiment.from_json(experiment_data)
    logger.info(f"Starting deployment of experiment {experiment_id}")

    # 2. find all prepared deployments per each connector
    deployments: dict[str, list[Deployment]] = defaultdict(list)
    for deployment in experiment.deployment_map:
        if not deployment.prepared:
            logger.info(
                f"Skipping deployment of not prepared executor {deployment.executor_id}, node {deployment.node}"
            )
            continue
        deployments[str(deployment.node["connector"])].append(deployment)

    # 3. check that all connectors are available
    for connector_name in deployments.keys():
        if connector_name not in connectors:
            return (
                500,
                f"Connector {connector_name} participating in the experiment {experiment_id} is not available, cannot proceed",
            )

    # 4. start background task to deploy
    background_tasks.add_task(
        background_deploy_task,
        username,
        experiment_id,
        deployments,
        experiment.deployment_context,
        netunicorn_authentication_context,
    )
    return 200, f"Deployment of experiment {experiment_id} started"


async def background_deploy_task(
    username: str,
    experiment_id: str,
    deployments: dict[str, list[Deployment]],
    deployment_context: Optional[dict[str, dict[str, str]]],
    netunicorn_authentication_context: Optional[dict[str, dict[str, str]]] = None,
) -> None:
    # 5. deploy on each connector
    for connector_name, connector_deployments in deployments.items():
        try:
            connector_deploy_context = None
            if deployment_context and connector_name in deployment_context:
                connector_deploy_context = deployment_context[connector_name]
            connector_auth_context = None
            if (
                netunicorn_authentication_context
                and connector_name in netunicorn_authentication_context
            ):
                connector_auth_context = netunicorn_authentication_context[
                    connector_name
                ]
            results = await connectors[connector_name].deploy(
                username,
                experiment_id,
                connector_deployments,
                connector_deploy_context,
                connector_auth_context,
            )
        except Exception as e:
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
            failure_reason = f"Connector {connector_name} raised an exception and deployment couldn't be completed"
            results = {
                deployment.executor_id: Failure(failure_reason)
                for deployment in connector_deployments
            }

        # each key in result is an executor id, value is Success or Failure with description
        # noinspection DuplicatedCode
        for executor_id, result in results.items():
            if isinstance(result, Success):
                logger.info(
                    f"Deployment of executor {executor_id} on connector {connector_name} succeeded"
                )
                continue

            failure_reason = str(result.failure())
            logger.warning(
                f"Deployment of executor {executor_id} on connector {connector_name} failed: {failure_reason}"
            )
            await db_connection_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                failure_reason,
                experiment_id,
                executor_id,
            )

    logger.info(f"Experiment {experiment_id} deployment finished")
    await db_connection_pool.execute(
        "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
        ExperimentStatus.READY.value,
        experiment_id,
    )


async def execute(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    execution_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_authentication_context: ConnectorContext = None,
) -> Tuple[int, str]:
    # 1. take experiment information from the database
    experiment_data: ExperimentRepresentation = await db_connection_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
        experiment_id,
    )
    if experiment_data is None:
        return 404, f"Experiment {experiment_id} not found"
    experiment: Experiment = Experiment.from_json(experiment_data)
    logger.info(f"Starting execution of experiment {experiment_id}")

    # There could be unprepared deployments and already finished executors:
    # 1.1. remove from deployment map all which executors already finished
    deployment_map = experiment.deployment_map
    finished_executors: Optional[list[Record]] = await db_connection_pool.fetch(
        "SELECT executor_id FROM executors WHERE experiment_id = $1 AND finished = TRUE",
        experiment_id,
    )
    if finished_executors:
        deployment_map = [
            deployment
            for deployment in deployment_map
            if deployment.executor_id not in finished_executors
        ]

    # 1.2. for each unprepared but not finished: set status to finished and error to "not prepared"
    for deployment in experiment.deployment_map:
        if not deployment.prepared:
            await db_connection_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                "Executor is not prepared",
                experiment_id,
                deployment.executor_id,
            )
    deployment_map = [
        deployment for deployment in deployment_map if deployment.prepared
    ]

    # 2. find all prepared deployments per each connector
    deployments: dict[str, list[Deployment]] = defaultdict(list)
    for deployment in deployment_map:
        deployments[str(deployment.node["connector"])].append(deployment)

    # 3. check that all connectors are available
    for connector_name in deployments.keys():
        if connector_name not in connectors:
            return (
                500,
                f"Connector {connector_name} participating in the experiment {experiment_id} is not available, cannot proceed",
            )

    # 4. start background task to execute
    background_tasks.add_task(
        background_execute_task,
        username,
        experiment_id,
        deployments,
        execution_context,
        netunicorn_authentication_context,
    )
    return 200, f"Execution of experiment {experiment_id} started"


async def background_execute_task(
    username: str,
    experiment_id: str,
    deployments: dict[str, list[Deployment]],
    execution_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_authentication_context: ConnectorContext = None,
) -> None:
    # 5. execute on each connector
    for connector_name, connector_deployments in deployments.items():
        try:
            connector_execution_context = None
            if execution_context and connector_name in execution_context:
                connector_execution_context = execution_context[connector_name]
            connector_auth_context = None
            if (
                netunicorn_authentication_context
                and connector_name in netunicorn_authentication_context
            ):
                connector_auth_context = netunicorn_authentication_context[
                    connector_name
                ]
            results = await connectors[connector_name].execute(
                username,
                experiment_id,
                connector_deployments,
                connector_execution_context,
                connector_auth_context,
            )
        except Exception as e:
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
            failure_reason = f"Connector {connector_name} raised an exception and execution couldn't be completed"
            results = {
                deployment.executor_id: Failure(failure_reason)
                for deployment in connector_deployments
            }

        # each key in result is an executor id, value is Success or Failure with description
        # noinspection DuplicatedCode
        for executor_id, result in results.items():
            if isinstance(result, Success):
                logger.info(
                    f"Execution of executor {executor_id} on connector {connector_name} succeeded"
                )
                continue

            failure_reason = str(result.failure())
            logger.warning(
                f"Execution of executor {executor_id} on connector {connector_name} failed: {failure_reason}"
            )
            await db_connection_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                failure_reason,
                experiment_id,
                executor_id,
            )

    logger.info(f"Experiment {experiment_id} execution started")


async def stop_execution(
    username: str,
    experiment_id: str,
    background_tasks: BackgroundTasks,
    cancellation_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_authentication_context: ConnectorContext = None,
) -> Tuple[int, str]:
    # TODO: implement
    return 500, "Not implemented"


async def stop_executors(
    username: str,
    executors: list[str],
    background_tasks: BackgroundTasks,
    cancellation_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_authentication_context: ConnectorContext = None,
) -> Tuple[int, str]:
    # find all connectors to ask and give them information about executors to stop
    # 1. find all executors
    executors_data: Optional[list[Record]] = await db_connection_pool.fetch(
        "SELECT executor_id, node_name, connector FROM executors WHERE executor_id = ANY($1)",
        executors,
    )
    if not executors_data:
        return 404, f"Executors {executors} not found"

    # 2. find all connectors
    executors_dict: dict[str, list[StopExecutorRequest]] = defaultdict(list)
    for line in executors_data:
        executors_dict[line["connector"]].append(
            {"executor_id": line["executor_id"], "node_name": line["node_name"]}
        )

    # 3. check that all connectors are available
    for connector_name, connector_executors in executors_dict.items():
        if connector_name not in connectors:
            logger.warning(
                f"Connector {connector_name} participating in the executors {connector_executors} is not available, cannot proceed"
            )
            return 500, f"Connector {connector_name} is not available, cannot proceed"

    # 4. start background task to stop executors
    background_tasks.add_task(
        background_stop_executors_task,
        username,
        executors_dict,
        cancellation_context,
        netunicorn_authentication_context,
    )
    return 200, f"Stopping executors {executors_dict} started"


async def background_stop_executors_task(
    username: str,
    executors: dict[str, list[StopExecutorRequest]],
    cancellation_context: Optional[dict[str, dict[str, str]]] = None,
    netunicorn_authentication_context: ConnectorContext = None,
) -> None:
    for connector_name, executors_list in executors.items():
        try:
            connector_cancellation_context = None
            if cancellation_context and connector_name in cancellation_context:
                connector_cancellation_context = cancellation_context[connector_name]
            connector_auth_context = None
            if (
                netunicorn_authentication_context
                and connector_name in netunicorn_authentication_context
            ):
                connector_auth_context = netunicorn_authentication_context[
                    connector_name
                ]
            results = await connectors[connector_name].stop_executors(
                username,
                executors_list,
                connector_cancellation_context,
                connector_auth_context,
            )
        except Exception as e:
            logger.warning(
                f"Connector {connector_name} raised an exception: {str(e.with_traceback(e.__traceback__))}"
            )
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
            failure_reason = f"Connector {connector_name} raised an exception and execution couldn't be completed"
            results = {
                stop_executor_request["executor_id"]: Failure(failure_reason)
                for stop_executor_request in executors_list
            }

        # each key in result is an executor id, value is Success or Failure with description
        for executor_id, result in results.items():
            if isinstance(result, Success):
                logger.info(
                    f"Stopping of executor {executor_id} on connector {connector_name} succeeded"
                )
                await db_connection_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE executor_id = $2",
                    "Executor was stopped",
                    executor_id,
                )
                continue

            failure_reason = str(result.failure())
            logger.warning(
                f"Stopping of executor {executor_id} on connector {connector_name} failed: {failure_reason}"
            )
            await db_connection_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE executor_id = $2",
                failure_reason,
                executor_id,
            )
