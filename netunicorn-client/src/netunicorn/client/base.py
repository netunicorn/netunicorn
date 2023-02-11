from typing import Iterable, Sequence
from abc import ABC, abstractmethod

from netunicorn.base.experiment import Experiment, ExperimentExecutionInformation
from netunicorn.base.nodes import Nodes


class BaseClient(ABC):

    @abstractmethod
    def get_nodes(self) -> Nodes:
        """
        This method returns description of available nodes in the system.
        :return: Nodes object with available nodes
        """
        pass

    @abstractmethod
    def get_experiments(self) -> Sequence[ExperimentExecutionInformation]:
        """
        This method returns information about all experiments that belong to the user.
        :return: list of ExperimentExecutionInformation objects
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_experiment_status(
        self, experiment_id: str
    ) -> ExperimentExecutionInformation:
        """
        Returns status and results of experiment.
        If experiment preparation succeed, you can explore map to see what nodes are prepared for deployment.
        If experiment finished, you can explore results of the experiment
        :param experiment_id: id of the experiment returned by 'deploy_map' function
        :return: current status of the experiment, optionally experiment definition, optionally experiment results
        """
        pass

    @abstractmethod
    def cancel_experiment(self, experiment_id: str) -> str:
        """
        Cancels experiment execution.
        :param experiment_id: id of the experiment
        """
        pass

    @abstractmethod
    def cancel_executors(self, executors: Iterable[str]) -> str:
        """
        Cancels particular executors.
        :param executors: list of executors to cancel
        """
        pass
