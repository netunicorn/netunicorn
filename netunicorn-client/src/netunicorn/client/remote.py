from typing import Dict, Union, Tuple

import cloudpickle
import requests as req

from .base import BaseClient

from netunicorn.base.experiment import Experiment, ExperimentExecutionResult, ExperimentStatus
from netunicorn.base.minions import MinionPool


class RemoteClientException(Exception):
    pass


class RemoteClient(BaseClient):
    def __init__(self, host: str, port: int, login: str, password: str):
        """
        Remote client for Unicorn.
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

    def prepare_deployment(self, deployment_map: Experiment, deployment_id: str) -> str:
        data = cloudpickle.dumps(deployment_map)
        result = req.post(
            f"{self.base_url}/api/v1/deployment/{deployment_id}/prepare",
            auth=(self.login, self.password),
            data=data
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to prepare deployment. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def start_execution(self, deployment_id: str) -> str:
        result = req.post(
            f"{self.base_url}/api/v1/deployment/{deployment_id}/start",
            auth=(self.login, self.password)
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to start deployment execution. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_deployment_status(self, deployment_id: str) -> Tuple[ExperimentStatus, Experiment]:
        result = req.get(f"{self.base_url}/api/v1/deployment/{deployment_id}", auth=(self.login, self.password))
        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            "Failed to get deployment status. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        ExperimentStatus,
        Union[Dict[str, ExperimentExecutionResult], Exception]
    ]:
        result = req.get(f"{self.base_url}/api/v1/deployment/{deployment_id}/result", auth=(self.login, self.password))
        if result.status_code == 200:
            return cloudpickle.loads(result.content)

        raise RemoteClientException(
            "Failed to get deployment result. "
            f"Status code: {result.status_code}, content: {result.content}"
        )
