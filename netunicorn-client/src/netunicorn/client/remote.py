import pickle

import cloudpickle
import requests as req
from typing import Dict, Union, Tuple, Optional, List

from netunicorn.base.experiment import Experiment, ExperimentExecutionResult, ExperimentStatus
from netunicorn.base.minions import MinionPool

from .base import BaseClient


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
        self.base_url = f"{host}:{port}"
        self.login = login
        self.password = password

    def get_minion_pool(self) -> MinionPool:
        result = req.get(f"{self.base_url}/api/v1/minion_pool", auth=(self.login, self.password))
        if result.status_code == 200:
            return pickle.loads(result.content)

        raise RemoteClientException(
            f"Failed to get minion pool. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def prepare_experiment(self, experiment: Experiment, experiment_id: str) -> str:
        data = pickle.dumps(experiment)
        result = req.post(
            f"{self.base_url}/api/v1/experiment/{experiment_id}/prepare",
            auth=(self.login, self.password),
            data=data
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to prepare an experiment. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def start_execution(self, experiment_id: str) -> str:
        result = req.post(
            f"{self.base_url}/api/v1/experiment/{experiment_id}/start",
            auth=(self.login, self.password)
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to start experiment execution. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def get_experiment_status(self, experiment_id: str) -> Tuple[
        ExperimentStatus,
        Optional[Experiment],
        Union[
            None,
            Exception,
            List[ExperimentExecutionResult]
        ]
    ]:
        result = req.get(f"{self.base_url}/api/v1/experiment/{experiment_id}", auth=(self.login, self.password))
        if result.status_code == 200:
            result = pickle.loads(result.content)
            if not (isinstance(result, tuple) and len(result) == 3):
                raise RemoteClientException(f"Invalid response from the server. Result: {result}")
            if isinstance(result[2], list):
                data = [cloudpickle.loads(v) for v in result[2]]
                result = (result[0], result[1], data)
            return result

        raise RemoteClientException(
            "Failed to get experiment status. "
            f"Status code: {result.status_code}, content: {result.content}"
        )
