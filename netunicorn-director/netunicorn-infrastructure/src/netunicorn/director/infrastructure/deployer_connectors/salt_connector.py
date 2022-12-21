import asyncio
import datetime
import functools
from typing import List, Optional

import asyncpg
from netunicorn.base.architecture import Architecture
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

    async def start_deployment(self, experiment_id: str) -> None:
        loop = asyncio.get_event_loop()
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
        for deployment in experiment:
            if not deployment.prepared:
                logger.debug(
                    f"Skipping deployment of not prepared executor {deployment.executor_id}, minion {deployment.minion}"
                )
                continue

            results = []
            try:
                if isinstance(deployment.environment_definition, DockerImage):
                    results = [
                        await loop.run_in_executor(
                            None,
                            functools.partial(
                                self.local.cmd,
                                deployment.minion.name,
                                "cmd.run",
                                arg=[
                                    (
                                        f"docker pull {deployment.environment_definition.image}",
                                    )
                                ],
                                timeout=300,
                                full_return=True,
                            ),
                        )
                    ]
                elif isinstance(deployment.environment_definition, ShellExecution):
                    results = [
                        await loop.run_in_executor(
                            None,
                            functools.partial(
                                self.local.cmd,
                                deployment.minion.name,
                                "cmd.run",
                                arg=[(command,)],
                                timeout=300,
                                full_return=True,
                            ),
                        )
                        for command in deployment.environment_definition.commands
                    ]
                else:
                    logger.error(
                        f"Unknown environment definition: {deployment.environment_definition}"
                    )
                    continue
            except Exception as e:
                logger.error(
                    f"Exception during deployment of executor {deployment.executor_id}, minion {deployment.minion}: {e}"
                )
                results.append(e)

            logger.debug(
                f"Deployment of executor {deployment.executor_id} to minion {deployment.minion}, result: {results}"
            )

            if not results or any(
                (
                    not result
                    or isinstance(result, Exception)
                    or not result[deployment.minion.name]
                    or result[deployment.minion.name]["retcode"] != 0
                )
                for result in results
            ):
                exception = f"Failed to create environment, see exception arguments for the log: {results}"
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

        logger.debug(f"Experiment {experiment_id} deployment successfully finished")
        await self.db_conn_pool.execute(
            "UPDATE experiments SET status = $1 WHERE experiment_id = $2",
            ExperimentStatus.READY.value,
            experiment_id,
        )

    async def start_execution(self, experiment_id: str):
        logger.debug(f"Starting execution of experiment {experiment_id}")
        loop = asyncio.get_event_loop()

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
        for deployment in experiment:
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
                continue

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

            executor_id = deployment.executor_id

            try:
                deployment.environment_definition.runtime_context.environment_variables[
                    "NETUNICORN_EXECUTOR_ID"
                ] = executor_id
                deployment.environment_definition.runtime_context.environment_variables[
                    "NETUNICORN_GATEWAY_ENDPOINT"
                ] = GATEWAY_ENDPOINT

                if isinstance(deployment.environment_definition, DockerImage):
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
                            f"-p {int(k)}:{int(v)}"
                            for k, v in deployment.environment_definition.runtime_context.ports_mapping.items()
                        )

                    runcommand = (
                        f"docker run -d "
                        f"" + env_vars + " " + ports + " "
                        f"--name {deployment.executor_id} "
                        f"{additional_arguments} "
                        f"{deployment.environment_definition.image}"
                    )
                    logger.debug("Starting executor with command: " + runcommand)

                    result = await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.local.cmd,
                            deployment.minion.name,
                            "cmd.run",
                            [(runcommand,)],
                            full_return=True,
                        ),
                    )
                elif isinstance(deployment.environment_definition, ShellExecution):
                    env_vars = " ".join(
                        f"{k}={v}"
                        for k, v in deployment.environment_definition.runtime_context.environment_variables.items()
                    )

                    runcommand = f"{env_vars} python3 -m netunicorn.executor"
                    logger.debug("Starting executor with command: " + runcommand)

                    result = await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.local.cmd_async,
                            deployment.minion.name,
                            "cmd.run",
                            [(runcommand,)],
                            full_return=True,
                        ),
                    )
                else:
                    exception = f"Unknown environment definition: {deployment.environment_definition}"
                    logger.error(exception)
                    await self.db_conn_pool.execute(
                        "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                        exception,
                        experiment_id,
                        deployment.executor_id,
                    )
                    continue
            except Exception as e:
                await self.db_conn_pool.execute(
                    "UPDATE executors SET finished = TRUE, error = $1 WHERE experiment_id = $2 AND executor_id = $3",
                    str(e),
                    experiment_id,
                    deployment.executor_id,
                )
                continue

            logger.debug(
                f"Result of starting executor {executor_id} on minion {deployment.minion}: {result}"
            )

        logger.debug(f"Experiment {experiment_id} execution successfully started")
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

        loop = asyncio.get_event_loop()
        minion_names = await self.db_conn_pool.fetch(
            "SELECT executor_id, minion_name FROM executors WHERE executor_id = ANY($1)",
            executors,
        )
        minion_names = {x["executor_id"]: x["minion_name"] for x in minion_names}

        for executor_id, minion_name in minion_names.items():
            await loop.run_in_executor(
                None,
                functools.partial(
                    self.local.cmd_async,
                    minion_name,
                    "cmd.run",
                    [(f"docker stop {executor_id}",)],
                ),
            )

        await self.db_conn_pool.executemany(
            "UPDATE executors SET finished = TRUE, error = $1 WHERE executor_id = $2",
            [(f"Executor was cancelled", executor_id) for executor_id in executors],
        )
