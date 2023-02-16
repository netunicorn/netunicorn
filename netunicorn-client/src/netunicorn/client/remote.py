import json
from typing import Iterable, Dict

import requests as req
from netunicorn.base.experiment import Experiment, ExperimentExecutionInformation
from netunicorn.base.nodes import Nodes
from netunicorn.base.utils import UnicornEncoder
from netunicorn.base.types import (
    NodesRepresentation,
    ExperimentExecutionInformationRepresentation,
)


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

    def healthcheck(self) -> bool:
        result = req.get(f"{self.endpoint}/health")
        if result.status_code == 200:
            return True

        raise RemoteClientException(
            f"The backend is not in healthy state. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def get_nodes(self) -> Nodes:
        result = req.get(
            f"{self.endpoint}/api/v1/nodes", auth=(self.login, self.password)
        )
        nodes: NodesRepresentation = result.json()
        if result.status_code == 200:
            return Nodes.dispatch_and_deserialize(nodes)

        raise RemoteClientException(
            f"Failed to get node pool. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def delete_experiment(self, experiment_name: str) -> None:
        result_data = req.delete(
            f"{self.endpoint}/api/v1/experiment/{experiment_name}",
            auth=(self.login, self.password),
        )
        if result_data.status_code != 200:
            raise RemoteClientException(
                f"Failed to delete the experiment {experiment_name}. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )

    def get_experiments(self) -> Dict[str, ExperimentExecutionInformation]:
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment",
            auth=(self.login, self.password),
        )
        if result_data.status_code != 200:
            raise RemoteClientException(
                "Failed to get experiments status. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )
        result: Dict[
            str, ExperimentExecutionInformationRepresentation
        ] = result_data.json()
        return {
            k: ExperimentExecutionInformation.from_json(v) for k, v in result.items()
        }

    def prepare_experiment(self, experiment: Experiment, experiment_id: str) -> str:
        data = json.dumps(experiment, cls=UnicornEncoder)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/prepare",
            auth=(self.login, self.password),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to prepare an experiment. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def start_execution(self, experiment_id: str) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/start",
            auth=(self.login, self.password),
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to start experiment execution. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def get_experiment_status(
        self, experiment_id: str
    ) -> ExperimentExecutionInformation:
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}",
            auth=(self.login, self.password),
        )
        if result_data.status_code != 200:
            raise RemoteClientException(
                "Failed to get experiment status. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )

        result: ExperimentExecutionInformationRepresentation = result_data.json()
        return ExperimentExecutionInformation.from_json(result)

    def cancel_experiment(self, experiment_id: str) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/cancel",
            auth=(self.login, self.password),
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to cancel experiment execution. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def cancel_executors(self, executors: Iterable[str]) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/executors/cancel",
            auth=(self.login, self.password),
            json=executors,
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to cancel provided executors. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )
