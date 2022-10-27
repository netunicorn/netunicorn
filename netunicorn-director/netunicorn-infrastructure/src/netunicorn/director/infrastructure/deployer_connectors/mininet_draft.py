import asyncio
import functools
import uuid
from typing import Dict

from cloudpickle import dumps
from netunicorn.base.environment_definitions import DockerImage, ShellExecution
from netunicorn.base.experiment import Experiment, ExperimentStatus
from netunicorn.base.minions import Minion, MinionPool

from ..resources import GATEWAY_ENDPOINT, logger, redis_connection


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
            host.cmd("dhclient &")
        logger.info("MininetConnector started")
        # h1, h4 = net.hosts[0], net.hosts[3]
        # h1.cmd('ping -c1 %s' % h4.IP())
        # net.stop()

    async def get_minion_pool(self) -> MinionPool:
        return MinionPool(
            [
                Minion(name=x.name, properties={"IP": x.IP(), "MAC": x.MAC()})
                for x in self.net.hosts
            ]
        )

    async def prepare_deployment(
        self, credentials: (str, str), deployment_map: Experiment, deployment_id: str
    ) -> None:

        for deployment in deployment_map:
            if not deployment.prepared:
                continue

            executor_id = str(uuid.uuid4())
            deployment.executor_id = executor_id
            await redis_connection.set(
                f"executor:{executor_id}:pipeline", dumps(deployment.pipeline)
            )

    async def start_execution(
        self, login: str, experiment: Experiment, experiment_id: str
    ) -> Dict[str, Minion]:
        loop = asyncio.get_event_loop()

        for deployment in experiment:
            if not deployment.prepared:
                continue

            executor_id = deployment.executor_id
            if isinstance(deployment.environment_definition, ShellExecution):
                host = [x for x in self.net.hosts if x.name == deployment.minion.name][
                    0
                ]
                host.waiting = False
                await loop.run_in_executor(
                    None,
                    functools.partial(
                        host.sendCmd,
                        f"NETUNICORN_EXECUTOR_ID={executor_id} "
                        f"NETUNICORN_GATEWAY_ENDPOINT={GATEWAY_ENDPOINT} "
                        f"python3 -m netunicorn.executor",
                    ),
                )
            else:
                logger.error(
                    f"Unknown environment definition: {deployment.environment_definition}"
                )
                continue

        exec_ids = {
            deployment.executor_id: (deployment.minion, deployment.pipeline)
            for deployment in experiment
        }
        await redis_connection.set(
            f"experiment:{experiment_id}:status", pickledumps(ExperimentStatus.RUNNING)
        )
        return exec_ids
