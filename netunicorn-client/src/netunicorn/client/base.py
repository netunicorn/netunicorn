from abc import ABC, abstractmethod
from typing import Dict, Iterable, Optional

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
    def get_experiments(self) -> Dict[str, ExperimentExecutionInformation]:
        """
        This method returns information about all experiments that belong to the user.
        :return: dictionary of experiment-name: ExperimentExecutionInformation
        """
        pass

    @abstractmethod
    def delete_experiment(self, experiment_name: str) -> None:
        """
        This method deletes experiment from the system or raise the exception if something's wrong.
        :param experiment_name: name of the experiment to delete
        """
        pass

    @abstractmethod
    def healthcheck(self) -> bool:
        """
        This method checks if the system is alive.
        :return: True if server is alive, raises exception otherwise
        """
        pass

    @abstractmethod
    def prepare_experiment(
        self,
        experiment: Experiment,
        experiment_id: str,
        deployment_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        """
        Prepares an Experiment. Server will start compiling and distributing the environment among nodes.
        You can check status of preparation by calling 'get_experiment_status' function and checking if it's in
        "READY" status.
        You need to provide a per-user unique experiment name.
        This method is network-failure-safe: subsequent calls with the same network name
        will not create additional deployment processes.
        :param experiment: experiment to prepare
        :param experiment_id: user-wide unique experiment name
        :param deployment_context: deployment context for connectors (see connectors documentation)
        Format: {connector_name: {key: value}, ...}
        :return: the same experiment_id if everything's correct
        """
        pass

    @abstractmethod
    def start_execution(
        self,
        experiment_id: str,
        execution_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        """
        Starts execution of prepared experiment.
        You can check status and results of an experiment by calling 'get_experiment_status' function and checking if it's in
        "FINISHED" status.
        You need to provide an experiment_id of prepared experiment to start.
        This method is network-failure-safe: subsequent calls with the same experiment id
        will not create additional start process.
        :param experiment_id: prepared experiment id
        :param execution_context: execution context for connectors (see connectors documentation)
        Format: {connector_name: {key: value}, ...}
        :return: the same experiment_id if execution already in progress or finished
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
        :param experiment_id: id of the experiment returned by 'prepare_experiment' function
        :return: current status of the experiment, optionally experiment definition, optionally experiment results
        """
        pass

    @abstractmethod
    def cancel_experiment(
        self,
        experiment_id: str,
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        """
        Cancels experiment execution.
        :param experiment_id: id of the experiment
        :param cancellation_context: cancellation context for connectors (see connectors documentation)
        Format: {connector_name: {key: value}, ...}
        :return: the same experiment_id if everything's correct
        """
        pass

    @abstractmethod
    def cancel_executors(
        self,
        executors: Iterable[str],
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        """
        Cancels particular executors.
        :param executors: list of executors to cancel
        :param cancellation_context: cancellation context for connectors (see connectors documentation)
        Format: {connector_name: {key: value}, ...}
        :return: the same experiment_id if everything's correct
        """
        pass
