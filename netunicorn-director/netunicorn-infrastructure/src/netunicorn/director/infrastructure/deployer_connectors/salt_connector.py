import asyncio
import datetime
from typing import List, Optional, Union

import asyncpg
from netunicorn.base.architecture import Architecture
from netunicorn.base.deployment import Deployment
from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.minions import Minion, MinionPool
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
)
from netunicorn.director.base.utils import __init_connection as _init_connection

from ..resources import GATEWAY_ENDPOINT, logger
from .base import Connector


class SaltConnector(Connector):
    PUBLIC_GRAINS = ["location", "osarch", "kernel"]

    def __init__(self):
        import salt.config
        import salt.runner

        self.master_opts = salt.config.client_config("/etc/salt/master")
        self.local = salt.client.LocalClient()
        # self.local.cmd(tgt, fun, arg=(), tgt_type='glob', full_return=False, kwarg=None, **kwargs)
        # self.local.cmd_async
        self.runner = salt.runner.RunnerClient(self.master_opts)
        # self.runner.cmd(fun, arg=None, pub_data=None, kwarg=None, print_event=True, full_return=False)
        self.db_conn_pool: Optional[asyncpg.Pool] = None

    @staticmethod
    def __all_salt_results_are_correct(results: list, minion_name: str) -> bool:
        return (
            # results are not empty
            bool(results)
            # each result is a dict and has minion name as a key
            and all(
                isinstance(x, dict) and x.get(minion_name, None) is not None
                for x in results
            )
            # all results have return code 0
            and all(
                isinstance(x[minion_name], dict)
                and x[minion_name].get("retcode", 1) == 0
                for x in results
            )
        )

    async def get_minion_pool(self) -> MinionPool:
        minions = self.local.cmd("*", "grains.item", arg=self.PUBLIC_GRAINS)
        minion_pool = MinionPool([])
        for minion_name, properties in minions.items():
            if not properties:
                continue
            instance = Minion(minion_name, properties)
            minion_architecture = f'{instance.properties.get("kernel", "").lower()}/{instance.properties.get("osarch", "").lower()}'
            try:
                instance.architecture = Architecture(minion_architecture)
            except Exception as e:
                logger.warning(
                    f"Unknown architecture {minion_architecture} for minion {instance.name}, {e}"
                )
                instance.architecture = Architecture.UNKNOWN
            minion_pool.append(instance)
        logger.debug(f"Returned minion pool length: {len(minion_pool)}")
        return minion_pool

    async def start_single_deployment(
        self, experiment_id: str, deployment: Deployment
    ) -> None:
        if not deployment.prepared:
            logger.debug(
                f"Skipping deployment of not prepared executor {deployment.executor_id}, minion {deployment.minion}"
            )
            return

        if type(deployment.environment_definition) not in {DockerImage, ShellExecution}:
            logger.error(
                f"Unknown environment definition: {deployment.environment_definition}"
            )
            return

        results: List[Union[dict, Exception]] = []
        commands = []
        if isinstance(deployment.environment_definition, DockerImage):
            commands = [f"docker pull {deployment.environment_definition.image}"]
        elif isinstance(deployment.environment_definition, ShellExecution):
            commands = deployment.environment_definition.commands

        try:
            results = [
                self.local.cmd(
                    deployment.minion.name,
                    "cmd.run",
                    arg=[(command,)],
                    timeout=300,
                    full_return=True,
                )
                for command in commands
            ]
        except Exception as e:
            logger.error(
                f"Exception during deployment of executor {deployment.executor_id}, minion {deployment.minion}: {e}"
            )
            results.append(e)

        logger.debug(
            f"Deployment of executor {deployment.executor_id} to minion {deployment.minion}, result: {results}"
        )

        if not self.__all_salt_results_are_correct(results, deployment.minion.name):
            exception = f"Failed to create environment, see exception arguments for the log: {results}"
            logger.error(exception)
            logger.debug(f"Deployment: {deployment}")
            await self.db_conn_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                exception,
                experiment_id,
                deployment.executor_id,
            )

        logger.info(
            f"Deployment of executor {deployment.executor_id} to minion {deployment.minion} finished successfully"
        )
        return

    async def start_deployment(self, experiment_id: str) -> None:
        experiment_data = await self.db_conn_pool.fetchval(
            "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if experiment_data is None:
            logger.error(f"Experiment {experiment_id} not found")
            return
        experiment: Experiment = Experiment.from_json(experiment_data)
        logger.debug(f"Starting deployment of experiment {experiment_id}")

        # stage 1: make every minion to create corresponding environment
        # (for docker: download docker image, for bare_metal - execute commands)
        await asyncio.gather(
            *[
                self.start_single_deployment(experiment_id, deployment)
                for deployment in experiment
            ]
        )

        logger.debug(f"Experiment {experiment_id} deployment successfully finished")
        await self.db_conn_pool.execute(
            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
            ExperimentStatus.READY.value,
            experiment_id,
        )

    async def start_single_execution(
        self, experiment_id: str, deployment: Deployment
    ) -> None:
        if not deployment.prepared:
            # You are not prepared!
            logger.debug(
                f"Deployment with executor {deployment.executor_id} is not prepared, skipping"
            )
            await self.db_conn_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                "Deployment is not prepared",
                experiment_id,
                deployment.executor_id,
            )
            return

        if await self.db_conn_pool.fetchval(
            "SELECT finished FROM executors WHERE experiment_id = $1 AND executor_id = $2",
            experiment_id,
            deployment.executor_id,
        ):
            # Already failed (probably during preparation step) or finished
            logger.warning(
                f"Executor {deployment.executor_id} of experiment {experiment_id} already finished"
            )
            return

        if type(deployment.environment_definition) not in {DockerImage, ShellExecution}:
            exception = (
                f"Unknown environment definition: {deployment.environment_definition}"
            )
            logger.error(exception)
            await self.db_conn_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                exception,
                experiment_id,
                deployment.executor_id,
            )
            return

        executor_id = deployment.executor_id

        # add required environment variables
        deployment.environment_definition.runtime_context.environment_variables[
            "NETUNICORN_EXECUTOR_ID"
        ] = executor_id
        deployment.environment_definition.runtime_context.environment_variables[
            "NETUNICORN_GATEWAY_ENDPOINT"
        ] = GATEWAY_ENDPOINT

        runcommand = "false"  # backup, just in case
        if isinstance(deployment.environment_definition, ShellExecution):
            env_vars = " ".join(
                f" {k}={v}"
                for k, v in deployment.environment_definition.runtime_context.environment_variables.items()
            )
            runcommand = f"{env_vars} python3 -m netunicorn.executor"
            logger.debug("Starting ShellExecution executor with command: " + runcommand)

        elif isinstance(deployment.environment_definition, DockerImage):
            env_vars = " ".join(
                f"-e {k}={v}"
                for k, v in deployment.environment_definition.runtime_context.environment_variables.items()
            )

            additional_arguments = " ".join(
                deployment.environment_definition.runtime_context.additional_arguments
            )

            ports = ""
            if deployment.environment_definition.runtime_context.ports_mapping:
                ports = " ".join(
                    f"-p {k}:{v}"
                    for k, v in deployment.environment_definition.runtime_context.ports_mapping.items()
                )

            runcommand = (
                f"docker run -d {env_vars} {ports} --name {deployment.executor_id} "
                f"{additional_arguments} {deployment.environment_definition.image}"
            )
            logger.debug("Starting Docker Image executor with command: " + runcommand)

        try:
            result = [
                self.local.cmd(
                    deployment.minion.name,
                    "cmd.run",
                    [(runcommand,)],
                    full_return=True,
                )
            ]
        except Exception as e:
            result = [e]

        if not self.__all_salt_results_are_correct(result, deployment.minion.name):
            logger.error(
                f"Failed to start executor {executor_id} on minion {deployment.minion}: {result}"
            )
            await self.db_conn_pool.execute(
                "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                str(result),
                experiment_id,
                deployment.executor_id,
            )
            return

        logger.info(
            f"Executor {executor_id} started successfully on minion {deployment.minion}"
        )
        logger.debug(
            f"Result of starting executor {executor_id} on minion {deployment.minion}: {result}"
        )

    async def start_execution(self, experiment_id: str):
        logger.info(f"Starting execution of experiment {experiment_id}")

        # get experiment from the db
        data = await self.db_conn_pool.fetchval(
            "SELECT data::jsonb FROM experiments WHERE experiment_id = $1",
            experiment_id,
        )
        if not data:
            error = Exception(f"Experiment {experiment_id} not found")
            await self.db_conn_pool.execute(
                "INSERT INTO experiments (experiment_id, status, error, experiment_name, creation_time, username) "
                "VALUES ($1, $2, $3, 'Unknown', NOW(), 'Unknown')",
                experiment_id,
                ExperimentStatus.FINISHED.value,
                error,
            )
            logger.error(error)
            return
        experiment = Experiment.from_json(data)

        # stage 2: make every minion to start corresponding environment
        # (for docker: start docker container, for bare_metal - start executor)
        await asyncio.gather(
            *[
                self.start_single_execution(experiment_id, deployment)
                for deployment in experiment
            ]
        )

        logger.info(f"Experiment {experiment_id} execution started")
        await self.db_conn_pool.execute(
            "UPDATE experiments SET status = $1, start_time = $2 WHERE experiment_id = $3",
            ExperimentStatus.RUNNING.value,
            datetime.datetime.utcnow(),
            experiment_id,
        )

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

    async def on_shutdown(self):
        await self.db_conn_pool.close()

    async def cancel_executors(self, executors: List[str]) -> None:
        if not executors:
            return

        minion_names = await self.db_conn_pool.fetch(
            "SELECT executor_id, minion_name FROM executors WHERE executor_id = ANY($1)",
            executors,
        )
        minion_names = {x["executor_id"]: x["minion_name"] for x in minion_names}

        # TODO: support ShellExecution
        for executor_id, minion_name in minion_names.items():
            logger.info(f"Stopping executor {executor_id} on minion {minion_name}")
            self.local.cmd_async(
                minion_name, "cmd.run", [(f"docker stop {executor_id}",)]
            )

        await self.db_conn_pool.executemany(
            "UPDATE executors SET finished = TRUE, error = $1 WHERE executor_id = $2",
            [(f"Executor was cancelled", executor_id) for executor_id in executors],
        )

    async def finalize_experiment(self, experiment_id: str) -> None:
        # TODO: implement stopping containers, deleting images, etc
        pass
