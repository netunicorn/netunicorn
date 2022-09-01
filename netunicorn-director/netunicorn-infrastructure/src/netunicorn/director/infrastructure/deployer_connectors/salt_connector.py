import asyncio
import functools

from returns.result import Failure
from pickle import dumps, loads

from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.minions import MinionPool, Minion
from ..resources import logger, redis_connection, GATEWAY_IP, GATEWAY_PORT

from .base import Connector


class SaltConnector(Connector):
    def __init__(self):
        import salt.config
        import salt.runner

        self.master_opts = salt.config.client_config('/etc/salt/master')
        self.local = salt.client.LocalClient()
        # self.local.cmd(tgt, fun, arg=(), tgt_type='glob', full_return=False, kwarg=None, **kwargs)
        # self.local.cmd_async
        self.runner = salt.runner.RunnerClient(self.master_opts)
        # self.runner.cmd(fun, arg=None, pub_data=None, kwarg=None, print_event=True, full_return=False)

    async def get_minion_pool(self) -> MinionPool:
        loop = asyncio.get_event_loop()
        minions = await loop.run_in_executor(None, functools.partial(self.runner.cmd, 'manage.up', print_event=False))
        return MinionPool([Minion(name=x, properties={}) for x in minions])

    async def start_deployment(self, experiment_id: str) -> None:
        loop = asyncio.get_event_loop()
        experiment_data = await redis_connection.get(f"experiment:{experiment_id}")
        if experiment_data is None:
            logger.error(f"Experiment {experiment_id} not found")
            return
        experiment: Experiment = loads(experiment_data)

        # stage 1: make every minion to create corresponding environment
        # (for docker: download docker image, for bare_metal - execute commands)
        for deployment in experiment:
            if not deployment.prepared:
                continue

            if isinstance(deployment.environment_definition, DockerImage):
                results = [await loop.run_in_executor(None, functools.partial(
                    self.local.cmd,
                    deployment.minion.name,
                    'cmd.run',
                    arg=[(f'docker pull {deployment.environment_definition.image}',)],
                    full_return=True
                ))]
            elif isinstance(deployment.environment_definition, ShellExecution):
                results = [
                    await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.local.cmd, deployment.minion.name, 'cmd.run', arg=[(command,)], full_return=True
                        )
                    )
                    for command in deployment.environment_definition.commands
                ]
            else:
                logger.error(f'Unknown environment definition: {deployment.environment_definition}')
                continue

            if results and all(len(x) == 0 for x in results):
                exception = Exception(f"Minion {deployment.minion.name} do not exist or is not responding")
                logger.exception(exception)
                logger.debug(f"Deployment: {deployment}")
                await redis_connection.set(
                    f"executor:{deployment.executor_id}:result",
                    dumps(Failure(exception))
                )

            if any(result[deployment.minion.name]['retcode'] != 0 for result in results):
                exception = Exception('Failed to create environment, see exception arguments for the log', results)
                logger.exception(exception)
                logger.debug(f"Deployment: {deployment}")
                await redis_connection.set(
                    f"executor:{deployment.executor_id}:result",
                    dumps(Failure(exception))
                )

        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.READY))

    async def start_execution(self, experiment_id: str):
        loop = asyncio.get_event_loop()

        # get experiment from redis
        data = await redis_connection.get(f"experiment:{experiment_id}")
        if not data:
            exception = Exception(f"Experiment {experiment_id} not found")
            await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.FINISHED))
            await redis_connection.set(f"experiment:{experiment_id}:result", dumps(exception))
            logger.exception(exception)
            return
        experiment: Experiment = loads(data)

        # stage 2: make every minion to start corresponding environment
        # (for docker: start docker container, for bare_metal - start executor)
        for deployment in experiment:
            if not deployment.prepared:
                # You are not prepared!
                await redis_connection.set(f"executor:{deployment.executor_id}:result", dumps(
                    (Failure([Exception("Deployment is not prepared")]), [])
                ))
                continue

            if await redis_connection.exists(f"executor:{deployment.executor_id}:result"):
                # Already failed (probably during preparation step) or finished
                logger.warning(f"Executor {deployment.executor_id} of experiment {experiment_id} already finished")
                continue

            executor_id = deployment.executor_id

            if isinstance(deployment.environment_definition, DockerImage):
                await loop.run_in_executor(None, functools.partial(
                    self.local.cmd,
                    deployment.minion.name,
                    'cmd.run',
                    [(f'docker run --rm -d '
                      f'-e NETUNICORN_EXECUTOR_ID={executor_id} '
                      f'-e NETUNICORN_GATEWAY_IP={GATEWAY_IP} '
                      f'-e NETUNICORN_GATEWAY_PORT={GATEWAY_PORT} '
                      f'{deployment.environment_definition.image}',)],
                    full_return=True,
                ))
            elif isinstance(deployment.environment_definition, ShellExecution):
                await loop.run_in_executor(None, functools.partial(
                    self.local.cmd_async,
                    deployment.minion.name,
                    'cmd.run',
                    [(f'NETUNICORN_EXECUTOR_ID={executor_id} '
                      f'NETUNICORN_GATEWAY_IP={GATEWAY_IP} '
                      f'NETUNICORN_GATEWAY_PORT={GATEWAY_PORT} '
                      f'python3 -m netunicorn.executor',)],
                    full_return=True,
                ))
            else:
                logger.error(f'Unknown environment definition: {deployment.environment_definition}')
                continue

        await redis_connection.set(f"experiment:{experiment_id}:status", dumps(ExperimentStatus.RUNNING))