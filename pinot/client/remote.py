from typing import Dict, Optional, Union, Tuple

import cloudpickle
import requests as req

from pinot.base import Pipeline
from pinot.base.deployment_map import DeploymentMap, DeploymentExecutionResult, DeploymentStatus
from pinot.base.minions import MinionPool
from pinot.client.base import BaseClient


class RemoteClientException(Exception):
    pass


class RemoteClient(BaseClient):
    def __init__(self, host: str, port: int, login: str, password: str):
        """
        Remote client for Pinot.
        :param host: Engine host.
        :param port: Engine port.
        :param login: Your login.
        :param password: Your password.
        """
        self.base_url = f"http://{host}:{port}"
        self.login = login
        self.password = password

    def get_minion_pool(self) -> MinionPool:
        result = req.get(f"{self.base_url}/api/v1/minion_pool", auth=(self.login, self.password))
        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            f"Failed to get minion pool. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def compile_pipeline(self, pipeline: Pipeline, environment_id: str) -> str:
        data = cloudpickle.dumps(pipeline)
        result = req.post(
            f"{self.base_url}/api/v1/compile/{environment_id}",
            auth=(self.login, self.password),
            data=data
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            f"Failed to start pipeline compilation. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_compiled_pipeline(self, environment_id: str) -> Optional[Pipeline]:
        result = req.get(f"{self.base_url}/api/v1/compile/{environment_id}", auth=(self.login, self.password))
        if result.status_code == 204:
            return None

        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            "Failed to get compilation result. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def deploy_map(self, deployment_map: DeploymentMap, deployment_id: str) -> str:
        data = cloudpickle.dumps(deployment_map)
        result = req.post(
            f"{self.base_url}/api/v1/deployment/{deployment_id}",
            auth=(self.login, self.password),
            data=data
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to deploy map. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        result = req.get(f"{self.base_url}/api/v1/deployment/{deployment_id}", auth=(self.login, self.password))
        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            "Failed to get deployment status. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        DeploymentStatus,
        Union[Dict[str, DeploymentExecutionResult], Exception]
    ]:
        result = req.get(f"{self.base_url}/api/v1/deployment/{deployment_id}/result", auth=(self.login, self.password))
        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            "Failed to get deployment result. "
            f"Status code: {result.status_code}, content: {result.content}"
        )
