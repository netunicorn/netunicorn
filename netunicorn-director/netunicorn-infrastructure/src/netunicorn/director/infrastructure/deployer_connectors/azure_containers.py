"""
netUnicorn connector for Azure Container Instances

Packets to install:
azure-mgmt-resource
azure-mgmt-containerinstance
azure-identity

Environment variables to provide:
AZURE_TENANT_ID
AZURE_CLIENT_ID
AZURE_CLIENT_SECRET
SUBSCRIPTION_ID
RESOURCE_GROUP_NAME
CONTAINER_LOCATION
"""
import asyncio

import os
import datetime
from typing import List, Optional

import asyncpg
from netunicorn.base.architecture import Architecture
from netunicorn.base.environment_definitions import DockerImage
from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.minions import MinionPool
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
)
from netunicorn.director.base.utils import __init_connection as _init_connection

from ..resources import GATEWAY_ENDPOINT, logger
from .base import Connector


class AzureContainerConnector(Connector):
    def __init__(self):
        from azure.identity import EnvironmentCredential
        from azure.mgmt.containerinstance import ContainerInstanceManagementClient

        # check existence of environment variables and raise error if not found
        self.azure_tenant_id = os.environ.get("AZURE_TENANT_ID")
        self.azure_client_id = os.environ.get("AZURE_CLIENT_ID")
        self.azure_client_secret = os.environ.get("AZURE_CLIENT_SECRET")
        self.subscription_id = os.environ.get("SUBSCRIPTION_ID")
        self.resource_group_name = os.environ.get("RESOURCE_GROUP_NAME")
        self.container_location = os.environ.get("CONTAINER_LOCATION")

        # noinspection PyTypeChecker
        self.client = ContainerInstanceManagementClient(
            credential=EnvironmentCredential(), subscription_id=self.subscription_id
        )

        self.db_conn_pool: Optional[asyncpg.Pool] = None

    async def __cleaner(self):
        """
        This is a temporary crutch for removing container groups for finished experiments.
        Yes, I'm ashamed of myself.
        But it's better than nothing for now, I'll implement a proper system-level finalization later.

        Theoretically, Azure Container Instances wouldn't charge for the container groups that are not running,
        but just in case.
        """
        logger.info("Starting Azure Container Instances cleaner")
        while True:
            try:
                container_groups = self.client.container_groups.list_by_resource_group(
                    self.resource_group_name
                )

                for group in container_groups:
                    executor_id = group.name
                    if await self.db_conn_pool.fetchval(
                        "SELECT finished FROM executors WHERE executor_id = $1",
                        executor_id,
                    ):
                        logger.info(
                            f"Removing container group {executor_id} from Azure Container Instances"
                        )
                        self.client.container_groups.begin_delete(
                            resource_group_name=self.resource_group_name,
                            container_group_name=executor_id,
                        ).result()

            except Exception as e:
                logger.error(f"Error while getting container groups: {e}")
                continue
            await asyncio.sleep(30)

    async def start_deployment(self, experiment_id: str) -> None:
        """
        Azure Container Instances automatically starts the container when it is created
        (seriously: https://stackoverflow.com/questions/67385581/deploying-azure-container-s-without-running-them),
        so this function only checks that all deployments are of DockerImage type,
        as it is the only type supported by Azure Container Instances.
        """

        experiment_data = await self.db_conn_pool.fetchval(
            "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if experiment_data is None:
            logger.error(f"Experiment {experiment_id} not found")
            return
        experiment: Experiment = Experiment.from_json(experiment_data)
        logger.debug(f"Starting deployment of experiment {experiment_id}")
        for deployment in experiment:
            if not deployment.prepared:
                logger.debug(
                    f"Skipping deployment of not prepared executor {deployment.executor_id}, minion {deployment.minion}"
                )
                continue

            if not isinstance(deployment.environment_definition, DockerImage):
                exception = (
                    f"Deployment of executor {deployment.executor_id} is not of type DockerImage "
                    f"(Azure Container Instances only supports DockerImage)"
                )
                logger.error(exception)
                logger.debug(f"Deployment: {deployment}")
                await self.db_conn_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                    exception,
                    experiment_id,
                    deployment.executor_id,
                )
                continue

            if deployment.minion.architecture != Architecture.LINUX_AMD64:
                exception = (
                    f"Deployment of executor {deployment.executor_id} is not of architecture "
                    f"{Architecture.LINUX_AMD64} (Azure Container Instances connector for now only supports "
                    f"{Architecture.LINUX_AMD64})"
                )
                logger.error(exception)
                logger.debug(f"Deployment: {deployment}")
                await self.db_conn_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                    exception,
                    experiment_id,
                    deployment.executor_id,
                )
                continue

            logger.debug(
                f"Deployment {deployment.minion} - {deployment.executor_id} successfully finished"
            )

        await self.db_conn_pool.execute(
            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
            ExperimentStatus.READY.value,
            experiment_id,
        )
        logger.debug(f"Experiment {experiment_id} deployment finished")

    async def _create_container_group(
        self, experiment_id: str, executor_id: str, container_group: dict
    ):
        # Create container group
        logger.debug(f"Creating container group {executor_id}")
        loop = asyncio.get_running_loop()
        try:
            request = self.client.container_groups.begin_create_or_update(
                resource_group_name=self.resource_group_name,
                container_group_name=executor_id,
                container_group=container_group,
            )
            await loop.run_in_executor(None, request.result)
        except Exception as e:
            logger.error(f"Container group creation failed: {e}")
            await self.db_conn_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                str(e),
                experiment_id,
                executor_id,
            )
            return

    async def start_execution(self, experiment_id: str) -> None:
        logger.info(f"Starting execution of experiment {experiment_id}")
        experiment_data = await self.db_conn_pool.fetchval(
            "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if experiment_data is None:
            logger.error(f"Experiment {experiment_id} not found")
            return
        experiment: Experiment = Experiment.from_json(experiment_data)

        deployments_to_start = []
        for deployment in experiment:
            # If not prepared - skip
            if not deployment.prepared:
                logger.debug(
                    f"Skipping execution of not prepared executor {deployment.executor_id}, minion {deployment.minion}"
                )
                await self.db_conn_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                    "Deployment is not prepared",
                    experiment_id,
                    deployment.executor_id,
                )
                continue

            # If already finished - skip
            if await self.db_conn_pool.fetchval(
                "SELECT finished FROM executors WHERE experiment_id = $1 AND executor_id = $2",
                experiment_id,
                deployment.executor_id,
            ):
                # Already failed (probably during preparation step) or finished
                logger.warning(
                    f"Executor {deployment.executor_id} of experiment {experiment_id} already finished"
                )
                continue

            deployments_to_start.append(deployment)

        if not deployments_to_start:
            logger.warning(
                f"No valid executors to deploy for experiment {experiment_id}"
            )
            await self.db_conn_pool.execute(
                "UPDATE experiments SET status = $1, start_time = $2 WHERE experiment_id = $3",
                ExperimentStatus.FINISHED.value,
                datetime.datetime.utcnow(),
                experiment_id,
            )
            return

        container_groups = {}
        for deployment in deployments_to_start:
            # Set required environment variables
            deployment.environment_definition.runtime_context.environment_variables[
                "NETUNICORN_EXECUTOR_ID"
            ] = deployment.executor_id
            deployment.environment_definition.runtime_context.environment_variables[
                "NETUNICORN_GATEWAY_ENDPOINT"
            ] = GATEWAY_ENDPOINT
            environment_variables = [
                {"name": x, "value": y}
                for x, y in deployment.environment_definition.runtime_context.environment_variables.items()
            ]

            # TODO: DNS names, ports mapping
            container_groups[deployment.executor_id] = {
                "location": self.container_location,
                "restart_policy": "Never",
                "os_type": "Linux",
                "containers": [
                    {
                        "name": deployment.executor_id,
                        "image": deployment.environment_definition.image,
                        "environment_variables": environment_variables,
                        "resources": {"requests": {"memory_in_gb": 1, "cpu": 1}},
                    }
                ],
            }

        await asyncio.gather(
            *[
                self._create_container_group(experiment_id, executor_id, group)
                for executor_id, group in container_groups.items()
            ]
        )

        # Update experiment status
        await self.db_conn_pool.execute(
            "UPDATE experiments SET status = $1, start_time = $2 WHERE experiment_id = $3",
            ExperimentStatus.RUNNING.value,
            datetime.datetime.utcnow(),
            experiment_id,
        )

    async def cancel_executors(self, executors: List[str]) -> None:
        """
        Azure Container Instances does not support stopping containers, but only the whole container group.
        So this function cancel the whole container group if all containers in it are to be cancelled,
        otherwise does nothing.
        """
        raise NotImplementedError()

    async def finalize_experiment(self, experiment_id: str) -> None:
        logger.debug(f"Cleaning resources for experiment {experiment_id}")

        experiment_data = await self.db_conn_pool.fetchval(
            "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if experiment_data is None:
            logger.error(f"Experiment {experiment_id} not found")
            return
        experiment: Experiment = Experiment.from_json(experiment_data)

        for deployment in experiment:
            try:
                self.client.container_groups.begin_delete(
                    resource_group_name=self.resource_group_name,
                    container_group_name=deployment.executor_id,
                ).result()
                logger.debug(f"Container group {deployment.executor_id} deleted")
            except Exception as e:
                logger.error(f"Container group deletion failed: {e}")

    async def get_minion_pool(self) -> MinionPool:
        # TODO: Implement
        return MinionPool([])

    async def healthcheck(self):
        await self.db_conn_pool.fetchval("SELECT 1")

    async def on_startup(self):
        self.db_conn_pool = await asyncpg.create_pool(
            host=DATABASE_ENDPOINT,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            database=DATABASE_DB,
            init=_init_connection,
        )

        asyncio.create_task(self.__cleaner())

    async def on_shutdown(self):
        await self.db_conn_pool.close()
