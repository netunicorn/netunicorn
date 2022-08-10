from typing import Dict, Tuple, Union

from pinot.base.experiment import Experiment, ExperimentStatus, ExperimentExecutionResult
from pinot.base.minions import MinionPool


class BaseClient:

    def get_minion_pool(self) -> MinionPool:
        """
        This method returns description of available minions in the system.
        :return: MinionPool with available minions
        """
        raise NotImplementedError()

    def prepare_deployment(self, deployment_map: Experiment, deployment_id: str) -> str:
        """
        Prepares a deployment map. Server will start compiling and distributing the environment among nodes.
        You can check status of preparation by calling 'get_deployment_status' function and checking if it's in
        "DeploymentStatus.READY" status.
        You need to provide a per-user unique deployment id.
        This method is network-failure-safe: subsequent calls with the same deployment id
        will not create additional deployment process.
        :param deployment_map: map to be prepared for deployment
        :param deployment_id: user-wide unique deployment id
        :return: the same deployment_id if preparation already in progress or finished.
        """
        raise NotImplementedError()

    def get_deployment_status(self, deployment_id: str) -> Tuple[ExperimentStatus, Experiment]:
        """
        Returns status of deployment and deployment map.
        If deployment preparation succeed, you can explore map to see what minions are prepared for deployment.
        :param deployment_id: id of the deployment returned by 'deploy_map' function
        :return: current status of deployment
        """
        raise NotImplementedError()

    def start_execution(self, deployment_id: str) -> str:
        """
        Starts execution of prepared deployment map.
        You can check status of deployment by calling 'get_deployment_status' function and checking if it's in
        "DeploymentStatus.FINISHED" status.
        You can retrieve results by calling 'get_deployment_result' function.
        You need to provide a per-user unique deployment id.
        This method is network-failure-safe: subsequent calls with the same deployment id
        will not create additional deployment process.
        :param deployment_id: prepared deployment id
        :return: the same deployment_id if execution already in progress or finished
        """
        raise NotImplementedError()

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        ExperimentStatus,
        Union[Dict[str, ExperimentExecutionResult], Exception]
    ]:
        """
        Returns result of the deployment execution.
        :param deployment_id: id of the deployment returned by 'deploy_map' function
        :return: status of deployment and result dict with executor ids as keys and DeploymentExecutionResult as values
        """
        raise NotImplementedError()
