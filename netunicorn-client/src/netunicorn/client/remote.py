import json
import pickle

import requests as req
from typing import Union, Tuple, Optional, List

from netunicorn.base.experiment import Experiment, ExperimentExecutionResult, ExperimentStatus
from netunicorn.base.minions import MinionPool
from netunicorn.base.utils import UnicornEncoder

from .base import BaseClient


class RemoteClientException(Exception):
    pass


class RemoteClient(BaseClient):
    def __init__(self, endpoint: str, login: str, password: str):
        """
        Remote client for Unicorn.
        :param endpoint: Unicorn installation endpoint.
        :param login: Unicorn installation login.
        :param password: Unicorn installation password.
        """
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        self.endpoint = endpoint
        self.login = login
        self.password = password

    def get_minion_pool(self) -> MinionPool:
        result = req.get(f"{self.endpoint}/api/v1/minion_pool", auth=(self.login, self.password))
        if result.status_code == 200:
            return MinionPool.from_json(result.json())

        raise RemoteClientException(
            f"Failed to get minion pool. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def prepare_experiment(self, experiment: Experiment, experiment_id: str) -> str:
        data = json.dumps(experiment, cls=UnicornEncoder)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/prepare",
            auth=(self.login, self.password),
            json=data
        )
        if result.status_code == 200:
            return result.content.decode()

        raise RemoteClientException(
            "Failed to prepare an experiment. "
            f"Status code: {result.status_code}, content: {result.content}"
        )

    def start_execution(self, experiment_id: str) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/start",
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
        result_data = req.get(f"{self.endpoint}/api/v1/experiment/{experiment_id}", auth=(self.login, self.password))
        if result_data.status_code == 200:
            result = result_data.json()
            if not (isinstance(result, list) and len(result) == 3):
                raise RemoteClientException(f"Invalid response from the server. Result: {result}")

            # decode experiment
            result[0] = ExperimentStatus.from_json(result[0])

            if result[1] is not None:
                result[1] = Experiment.from_json(result[1])

            # decode execution results
            if isinstance(result[2], str):
                result[2] = Exception(result[2])

            if isinstance(result[2], list):
                result[2] = [
                    pickle.loads(x) for x in result[2]
                ]

            return tuple(result)

        raise RemoteClientException(
            "Failed to get experiment status. "
            f"Status code: {result_data.status_code}, content: {result_data.content}"
        )
