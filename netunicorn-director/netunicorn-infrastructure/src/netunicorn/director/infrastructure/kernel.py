from __future__ import annotations

import importlib
import os
from collections import defaultdict
from logging import Logger
from typing import Union, Any, Tuple, Optional

import asyncpg
import yaml
from asyncpg import Record
from fastapi import BackgroundTasks
from netunicorn.base.deployment import Deployment
from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.nodes import CountableNodePool, Nodes
from netunicorn.director.base.resources import LOGGING_LEVELS, get_logger
from netunicorn.director.base.utils import __init_connection
from returns.result import Failure, Success

from .connectors.protocol import NetunicornConnectorProtocol
from .connectors.types import StopExecutorRequest

logger: Logger
db_connection_pool: asyncpg.pool.Pool
connectors: dict[str, NetunicornConnectorProtocol] = {}


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
        logger.error(f"Failed to initialize connector {connector_name}: {e}")
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
        os.environ.get("NETUNICORN_INFRASTRUCTURE_LOG_LEVEL", False)
        or config.get("netunicorn.infrastructure.log.level", False)
        or "info"
    )
    logger_level = config["netunicorn.infrastructure.log.level"].upper()
    if logger_level not in LOGGING_LEVELS:
        raise ValueError(f"Invalid log level {logger_level}")
    logger = get_logger(
        "netunicorn.director.infrastructure", LOGGING_LEVELS[logger_level]
    )
    logger.info(f"Logger initialized, level: {logger_level}")

    # module host and port
    config["netunicorn.infrastructure.host"] = (
        os.environ.get("NETUNICORN_INFRASTRUCTURE_HOST", False)
        or config.get("netunicorn.infrastructure.host", False)
        or "127.0.0.1"
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
    global db_connection_pool, connectors

    db_connection_pool = await asyncpg.create_pool(
        host=config["netunicorn.database.endpoint"],
        user=config["netunicorn.database.user"],
        password=config["netunicorn.database.password"],
        database=config["netunicorn.database.db"],
        init=__init_connection,
    )
    await db_connection_pool.fetchval("SELECT 1")

    connectors_config = config.get("netunicorn.infrastructure.connectors", {})
    if len(connectors_config) == 0:
        logger.warning("No connectors configured")

    for connector_name, connector_config in connectors_config.items():
        await initialize_connector(
            connector_name, connector_config, config["netunicorn.gateway.endpoint"]
        )

    return


async def health() -> Tuple[int, str]:
    statuses: list[Tuple[str, bool, str]] = []
    try:
        await db_connection_pool.fetchval("SELECT 1")
        statuses.append(("database", True, "OK"))
    except Exception as e:
        statuses.append(("database", False, str(e)))

    for connector_name, connector in connectors.items():
        try:
            status, description = await connector.health()
        except Exception as e:
            status, description = False, str(e)
            logger.warning(f"Connector {connector_name} raised an exception: {e}")
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
            logger.warning(f"Connector {connector_name} raised an exception: {e}")


async def get_nodes(username: str) -> Tuple[int, Union[Nodes, str]]:
    pools = []
    for connector_name, connector in connectors.items():
        try:
            nodes = await connector.get_nodes(username)
            nodes.set_property("connector", connector_name)
            pools.append(nodes)
        except Exception as e:
            logger.warning(f"Connector {connector_name} raised an exception: {e}")
            logger.warning(f"Connector {connector_name} moved to unavailable status.")
            connectors.pop(connector_name)
    pools = CountableNodePool(nodes=pools)
    return 200, pools


async def deploy(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Tuple[int, str]:
    # 1. take experiment information from the database
    experiment_data: Optional[dict[str, Any]] = await db_connection_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
        experiment_id,
    )
    if experiment_data is None:
        return 404, f"Experiment {experiment_id} not found"

    experiment: Experiment = Experiment.from_json(experiment_data)
    logger.debug(f"Starting deployment of experiment {experiment_id}")

    # 2. find all prepared deployments per each connector
    deployments: dict[str, list[Deployment]] = defaultdict(list)
    for deployment in experiment.deployment_map:
        if not deployment.prepared:
            logger.debug(
                f"Skipping deployment of not prepared executor {deployment.executor_id}, node {deployment.node}"
            )
            continue
        deployments[deployment.node["connector"]].append(deployment)

    # 3. check that all connectors are available
    for connector_name in deployments.keys():
        if connector_name not in connectors:
            return (
                500,
                f"Connector {connector_name} participating in the experiment {experiment_id} is not available, cannot proceed",
            )

    # 4. start background task to deploy
    background_tasks.add_task(
        background_deploy_task, username, experiment_id, deployments
    )
    return 200, f"Deployment of experiment {experiment_id} started"


async def background_deploy_task(
    username: str, experiment_id: str, deployments: dict[str, list[Deployment]]
) -> None:
    # 5. deploy on each connector
    for connector_name, connector_deployments in deployments.items():
        try:
            results = await connectors[connector_name].deploy(
                username, experiment_id, connector_deployments
            )
        except Exception as e:
            logger.warning(f"Connector {connector_name} raised an exception: {e}")
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
                logger.debug(
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

    logger.debug(f"Experiment {experiment_id} deployment finished")
    await db_connection_pool.execute(
        "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
        ExperimentStatus.READY.value,
        experiment_id,
    )


async def execute(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Tuple[int, str]:
    # 1. take experiment information from the database
    experiment_data: Optional[dict[str, Any]] = await db_connection_pool.fetchval(
        "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
        experiment_id,
    )
    if experiment_data is None:
        return 404, f"Experiment {experiment_id} not found"
    experiment: Experiment = Experiment.from_json(experiment_data)
    logger.debug(f"Starting execution of experiment {experiment_id}")

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
        deployments[deployment.node["connector"]].append(deployment)

    # 3. check that all connectors are available
    for connector_name in deployments.keys():
        if connector_name not in connectors:
            return (
                500,
                f"Connector {connector_name} participating in the experiment {experiment_id} is not available, cannot proceed",
            )

    # 4. start background task to execute
    background_tasks.add_task(
        background_execute_task, username, experiment_id, deployments
    )
    return 200, f"Execution of experiment {experiment_id} started"


async def background_execute_task(
    username: str, experiment_id: str, deployments: dict[str, list[Deployment]]
) -> None:
    # 5. execute on each connector
    for connector_name, connector_deployments in deployments.items():
        try:
            results = await connectors[connector_name].execute(
                username, experiment_id, connector_deployments
            )
        except Exception as e:
            logger.warning(f"Connector {connector_name} raised an exception: {e}")
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
                logger.debug(
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

    logger.debug(f"Experiment {experiment_id} execution started")


async def stop_execution(
    username: str, experiment_id: str, background_tasks: BackgroundTasks
) -> Tuple[int, str]:
    # TODO: implement
    return 500, "Not implemented"


async def stop_executors(
    username: str, executors: list[str], background_tasks: BackgroundTasks
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
    background_tasks.add_task(background_stop_executors_task, username, executors_dict)
    return 200, f"Stopping executors {executors_dict} started"


async def background_stop_executors_task(
    username: str, executors: dict[str, list[StopExecutorRequest]]
) -> None:
    for connector_name, executors_list in executors.items():
        try:
            results = await connectors[connector_name].stop_executors(
                username, executors_list
            )
        except Exception as e:
            logger.warning(f"Connector {connector_name} raised an exception: {e}")
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
                logger.debug(
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
