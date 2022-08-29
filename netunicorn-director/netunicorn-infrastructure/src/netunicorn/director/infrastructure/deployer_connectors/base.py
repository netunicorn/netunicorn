from netunicorn.base.experiment import Experiment
from netunicorn.base.minions import MinionPool


class Connector:
    async def get_minion_pool(self) -> MinionPool:
        raise NotImplementedError()

    async def start_deployment(self, deployment_id: str, experiment: Experiment) -> None:
        raise NotImplementedError()

    async def start_execution(self, deployment_id: str) -> None:
        raise NotImplementedError()