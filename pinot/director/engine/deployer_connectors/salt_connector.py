import asyncio
import functools
import os
import uuid
from typing import Dict

from returns.result import Failure
from cloudpickle import dumps

from pinot.base.deployment_map import DeploymentMap, DeploymentStatus
from pinot.base.environment_definitions import DockerImage, ShellExecution
from pinot.base.minions import MinionPool, Minion
from pinot.director.engine.resources import logger, redis_connection, GATEWAY_IP, GATEWAY_PORT


class SaltConnector:
    def __init__(self):
        import salt.config
        import salt.runner

        self.master_opts = salt.config.client_config('/etc/salt/master')
        self.local = salt.client.LocalClient()
        # self.local.cmd(tgt, fun, arg=(), tgt_type='glob', full_return=False, kwarg=None, **kwargs)
        # self.local.cmd_async
        self.runner = salt.runner.RunnerClient(self.master_opts)
        # self.runner.cmd(fun, arg=None, pub_data=None, kwarg=None, print_event=True, full_return=False)
        pass

    async def get_minion_pool(self) -> MinionPool:
        loop = asyncio.get_event_loop()
        minions = await loop.run_in_executor(None, functools.partial(self.runner.cmd, 'manage.up', print_event=False))
        return MinionPool([Minion(name=x, properties={}) for x in minions])

    async def prepare_deployment(
            self, credentials: (str, str), deployment_map: DeploymentMap, deployment_id: str
    ) -> None:
        loop = asyncio.get_event_loop()

        # stage 0: create IDs for each future executor and set pipelines to redis
        for deployment in deployment_map:
            if not deployment.prepared:
                continue

            executor_id = str(uuid.uuid4())
            deployment.executor_id = executor_id
            await redis_connection.set(f"executor:{executor_id}:pipeline", dumps(deployment.pipeline))

        # stage 1: make every minion to create corresponding environment
        # (for docker: download docker image, for bare_metal - execute commands)
        for deployment in deployment_map:
            if not deployment.prepared:
                continue

            if isinstance(deployment.pipeline.environment_definition, DockerImage):
                results = [await loop.run_in_executor(None, functools.partial(
                    self.local.cmd,
                    deployment.minion.name,
                    'cmd.run',
                    arg=[(f'docker pull {deployment.pipeline.environment_definition.image}',)],
                    full_return=True
                ))]
            elif isinstance(deployment.pipeline.environment_definition, ShellExecution):
                results = [
                    await loop.run_in_executor(
                        None,
                        functools.partial(
                            self.local.cmd, deployment.minion.name, 'cmd.run', arg=[(command,)], full_return=True
                        )
                    )
                    for command in deployment.pipeline.environment_definition.commands
                ]
            else:
                logger.error(f'Unknown environment definition: {deployment.pipeline.environment_definition}')
                continue

            if results and all(len(x) == 0 for x in results):
                deployment.prepared = False
                exception = Exception(f"Minion {deployment.minion.name} do not exist or is not responding")
                logger.exception(exception)
                logger.debug(f"Deployment: {deployment}")
                await redis_connection.set(
                    f"executor:{deployment.executor_id}:result",
                    dumps(Failure(exception))
                )

            if any(result[deployment.minion.name]['retcode'] != 0 for result in results):
                deployment.prepared = False
                exception = Exception('Failed to create environment, see exception arguments for the log', results)
                logger.exception(exception)
                logger.debug(f"Deployment: {deployment}")
                await redis_connection.set(
                    f"executor:{deployment.executor_id}:result",
                    dumps(Failure(exception))
                )

    async def start_execution(self, login: str, deployment_map: DeploymentMap, deployment_id: str) -> Dict[str, Minion]:
        loop = asyncio.get_event_loop()

        # stage 2: make every minion to start corresponding environment
        # (for docker: start docker container, for bare_metal - start executor)
        for deployment in deployment_map:
            if not deployment.prepared:
                # You are not prepared!
                continue

            executor_id = deployment.executor_id

            if isinstance(deployment.pipeline.environment_definition, DockerImage):
                await loop.run_in_executor(None, functools.partial(
                    self.local.cmd,
                    deployment.minion.name,
                    'cmd.run',
                    [(f'docker run --rm -d '
                      f'-e PINOT_EXECUTOR_ID={executor_id} '
                      f'-e PINOT_GATEWAY_IP={GATEWAY_IP} '
                      f'-e PINOT_GATEWAY_PORT={GATEWAY_PORT} '
                      f'{deployment.pipeline.environment_definition.image}',)],
                    full_return=True,
                ))
            elif isinstance(deployment.pipeline.environment_definition, ShellExecution):
                await loop.run_in_executor(None, functools.partial(
                    self.local.cmd_async,
                    deployment.minion.name,
                    'cmd.run',
                    [(f'PINOT_EXECUTOR_ID={executor_id} '
                      f'PINOT_GATEWAY_IP={GATEWAY_IP} '
                      f'PINOT_GATEWAY_PORT={GATEWAY_PORT} '
                      f'python3 -m pinot.executor.executor',)],
                    full_return=True,
                ))
            else:
                logger.error(f'Unknown environment definition: {deployment.pipeline.environment_definition}')
                continue

        exec_ids = {deployment.executor_id: (deployment.minion, deployment.pipeline) for deployment in deployment_map}
        await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(DeploymentStatus.RUNNING))
        return exec_ids


class SaltLocalConnector(SaltConnector):
    pass


class SaltRemoteConnector:
    def __init__(self):
        self.CHERRY_PY_ENDPOINT = os.environ.get('SALT_CHERRY_PY_ENDPOINT', 'https://172.17.0.1/api/v1/direct/')
        self.CHERRY_PY_USERNAME = os.environ['SALT_CHERRY_PY_USERNAME']
        self.CHERRY_PY_PASSWORD = os.environ['SALT_CHERRY_PY_PASSWORD']
        # TODO: finish
