from typing import Dict, Optional, Tuple, Union

from pinot.base import Pipeline
from pinot.base.deployment_map import DeploymentMap, DeploymentStatus, DeploymentExecutionResult
from pinot.base.minions import MinionPool


class BaseClient:

    def get_minion_pool(self) -> MinionPool:
        """
        This method returns description of available minions in the system.
        :return: MinionPool with available minions
        """
        raise NotImplementedError()

    def compile_pipeline(self, pipeline: Pipeline, environment_id: str) -> str:
        """
        Prepares an environment: preprocess and compile the pipeline.
        You need to provide a per-user unique environment id.
        This method is network-failure-safe: subsequent calls with the same environment id
        will not create additional environment preparations process.
        :param pipeline: pipeline to prepare environment for
        :param environment_id: unique environment id
        :return: the same environment_id if preparation started or is already in progress
        """
        raise NotImplementedError()

    def get_compiled_pipeline(self, environment_id: str) -> Optional[Pipeline]:
        """
        Returns deployment map for a compiled pipeline.
        This deployment map sometimes will have something already added by pipeline preprocessors.
        :param environment_id: compilation id received from compile_pipeline
        :return: None if preparation is not finished, otherwise DeploymentMap you can use for deployment of pipelines
        """
        raise NotImplementedError()

    def deploy_map(self, deployment_map: DeploymentMap, deployment_id: str) -> str:
        """
        Deploys a deployment map. Server will start distributing the environment and pipeline execution.
        You can check status of deployment by calling 'get_deployment_status' function.
        You can retrieve results by calling 'get_deployment_result' function.
        You need to provide a per-user unique deployment id.
        This method is network-failure-safe: subsequent calls with the same deployment id
        will not create additional deployment process.
        :param deployment_map: map to be deployed
        :param deployment_id: unique deployment id
        :return: the same deployment_id if deployment started or already in progress
        """
        raise NotImplementedError()

    def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        """
        Returns status of deployment.
        :param deployment_id: id of the deployment returned by 'deploy_map' function
        :return: current status of deployment
        """
        raise NotImplementedError()

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        DeploymentStatus,
        Union[Dict[str, DeploymentExecutionResult], Exception]
    ]:
        """
        Returns result of the deployment execution.
        :param deployment_id: id of the deployment returned by 'deploy_map' function
        :return: status of deployment and result dict with executor ids as keys and DeploymentExecutionResult as values
        """
        raise NotImplementedError()
