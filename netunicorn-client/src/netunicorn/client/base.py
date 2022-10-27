from typing import Iterable

from netunicorn.base.experiment import Experiment, ExperimentExecutionInformation
from netunicorn.base.minions import MinionPool


class BaseClient:
    def get_minion_pool(self) -> MinionPool:
        """
        This method returns description of available minions in the system.
        :return: MinionPool with available minions
        """
        raise NotImplementedError()

    def prepare_experiment(self, experiment: Experiment, experiment_id: str) -> str:
        """
        Prepares a deployment map. Server will start compiling and distributing the environment among nodes.
        You can check status of preparation by calling 'get_deployment_status' function and checking if it's in
        "DeploymentStatus.READY" status.
        You need to provide a per-user unique deployment id.
        This method is network-failure-safe: subsequent calls with the same deployment id
        will not create additional deployment process.
        :param experiment: map to be prepared for deployment
        :param experiment_id: user-wide unique deployment id
        :return: the same deployment_id if preparation already in progress or finished.
        """
        raise NotImplementedError()

    def start_execution(self, experiment_id: str) -> str:
        """
        Starts execution of prepared deployment map.
        You can check status of deployment by calling 'get_deployment_status' function and checking if it's in
        "DeploymentStatus.FINISHED" status.
        You can retrieve results by calling 'get_deployment_result' function.
        You need to provide a per-user unique deployment id.
        This method is network-failure-safe: subsequent calls with the same deployment id
        will not create additional deployment process.
        :param experiment_id: prepared deployment id
        :return: the same deployment_id if execution already in progress or finished
        """
        raise NotImplementedError()

    def get_experiment_status(
        self, experiment_id: str
    ) -> ExperimentExecutionInformation:
        """
        Returns status and results of experiment.
        If experiment preparation succeed, you can explore map to see what minions are prepared for deployment.
        If experiment finished, you can explore results of the experiment
        :param experiment_id: id of the experiment returned by 'deploy_map' function
        :return: current status of the experiment, optionally experiment definition, optionally experiment results
        """
        raise NotImplementedError()

    def cancel_experiment(self, experiment_id: str) -> str:
        """
        Cancels experiment execution.
        :param experiment_id: id of the experiment
        """
        raise NotImplementedError()

    def cancel_executors(self, executors: Iterable[str]) -> str:
        """
        Cancels particular executors.
        :param executors: list of executors to cancel
        """
        raise NotImplementedError()
