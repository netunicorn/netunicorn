from typing import List

from netunicorn.base.minions import MinionPool


class Connector:
    async def get_minion_pool(self) -> MinionPool:
        """
        Returns a minion pool for experiments to be executed on.
        """
        raise NotImplementedError()

    async def start_deployment(self, experiment_id: str) -> None:
        """
        Starts a deployment of the experiment to the infrastructure.
        """
        raise NotImplementedError()

    async def start_execution(self, experiment_id: str) -> None:
        """
        Starts the execution of the experiment on the infrastructure.
        """
        raise NotImplementedError()

    async def cancel_executors(self, executors: List[str]) -> None:
        """
        Cancels all executors in the list.
        """
        raise NotImplementedError()

    async def finalize_experiment(self, experiment_id: str) -> None:
        """
        Finalizes the experiment, clean resources, etc.
        """
        raise NotImplementedError()

    async def healthcheck(self):
        """
        Checks if the connector is alive.
        """
        raise NotImplementedError()

    async def on_startup(self):
        """
        Called when the connector is started.
        """
        raise NotImplementedError()

    async def on_shutdown(self):
        """
        Called when the connector is shutdown.
        """
        raise NotImplementedError()
