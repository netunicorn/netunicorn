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


class MininetConnector:
    """
    Draft connector version for demonstrating ability to deploy to fixed topology in Mininet
    """

    def __init__(self):
        logger.info("Using MininetConnector")
        from mininet.net import Mininet
        from mininet.topolib import TreeTopo

        self.tree = TreeTopo(depth=2, fanout=2)
        self.net = Mininet(topo=self.tree)
        self.net.addNAT().configDefault()
        self.net.start()
        for host in self.net.hosts:
            host.cmd('dhclient')
        # h1, h4 = net.hosts[0], net.hosts[3]
        # h1.cmd('ping -c1 %s' % h4.IP())
        # net.stop()

    async def get_minion_pool(self) -> MinionPool:
        return MinionPool([Minion(name=x.name, properties={'IP': x.IP(), 'MAC': x.MAC()}) for x in self.net.hosts])

    async def prepare_deployment(
            self, credentials: (str, str), deployment_map: DeploymentMap, deployment_id: str
    ) -> None:
        
        for deployment in deployment_map:
            if not deployment.prepared:
                continue

            executor_id = str(uuid.uuid4())
            deployment.executor_id = executor_id
            await redis_connection.set(f"executor:{executor_id}:pipeline", dumps(deployment.pipeline))

    async def start_execution(self, login: str, deployment_map: DeploymentMap, deployment_id: str) -> Dict[str, Minion]:
        loop = asyncio.get_event_loop()

        for deployment in deployment_map:
            if not deployment.prepared:
                continue

            executor_id = deployment.executor_id
            if isinstance(deployment.pipeline.environment_definition, ShellExecution):
                host = [x for x in self.net.hosts if x.name == deployment.minion.name][0]
                await loop.run_in_executor(None, functools.partial(
                    host.sendCmd,
                    f'PINOT_EXECUTOR_ID={executor_id} '
                    f'PINOT_GATEWAY_IP={GATEWAY_IP} '
                    f'PINOT_GATEWAY_PORT={GATEWAY_PORT} '
                    f'python3 -m pinot.executor.executor'
                ))
            else:
                logger.error(f'Unknown environment definition: {deployment.pipeline.environment_definition}')
                continue

        exec_ids = {deployment.executor_id: (deployment.minion, deployment.pipeline) for deployment in deployment_map}
        await redis_connection.set(f"{login}:deployment:{deployment_id}:status", dumps(DeploymentStatus.RUNNING))
        return exec_ids
