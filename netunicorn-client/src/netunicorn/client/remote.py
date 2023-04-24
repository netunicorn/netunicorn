import json
import warnings
from typing import Dict, Iterable, Optional
from urllib.parse import quote_plus

import requests as req
from netunicorn.base.experiment import Experiment, ExperimentExecutionInformation
from netunicorn.base.nodes import Nodes
from netunicorn.base.types import (
    ExperimentExecutionInformationRepresentation,
    FlagValues,
    NodesRepresentation,
)
from netunicorn.base.utils import UnicornEncoder

from .base import BaseClient


class RemoteClientException(Exception):
    pass


class RemoteClient(BaseClient):
    def __init__(
        self,
        endpoint: str,
        login: str,
        password: str,
        authentication_context: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        """
        Remote client for Unicorn.
        :param endpoint: Unicorn installation endpoint.
        :param login: Unicorn installation login.
        :param password: Unicorn installation password.
        :param authentication_context: Authentication context for connectors.
        E.g., if a connector A requires users to provide additional security token, it could be specified here.
        Format: {connector_name: {key: value}}
        """
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        self.endpoint = endpoint
        self.login = login
        self.password = password
        self.authentication_context = authentication_context or {}

    @staticmethod
    def quote_plus_and_warn(string: str) -> str:
        result = quote_plus(string)
        if result != string:
            warnings.warn(
                f"String {string} was encoded to {result}. "
                f"Consider using only alphanumeric characters and underscores."
            )

        return result

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
            f"{self.endpoint}/api/v1/nodes",
            auth=(self.login, self.password),
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
        )
        if result.status_code == 200:
            nodes: NodesRepresentation = result.json()
            return Nodes.dispatch_and_deserialize(nodes)

        raise RemoteClientException(
            f"Failed to get node pool. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def delete_experiment(self, experiment_name: str) -> None:
        experiment_name = self.quote_plus_and_warn(experiment_name)
        result_data = req.delete(
            f"{self.endpoint}/api/v1/experiment/{experiment_name}",
            auth=(self.login, self.password),
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
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
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
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

    def prepare_experiment(
        self,
        experiment: Experiment,
        experiment_id: str,
        deployment_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        if deployment_context is not None:
            if experiment.deployment_context is None:
                experiment.deployment_context = {}
            experiment.deployment_context.update(deployment_context)

        experiment_id = self.quote_plus_and_warn(experiment_id)
        data = json.dumps(experiment, cls=UnicornEncoder)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/prepare",
            auth=(self.login, self.password),
            data=data,
            headers={
                "Content-Type": "application/json",
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                ),
            },
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to prepare an experiment. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def start_execution(
        self,
        experiment_id: str,
        execution_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        experiment_id = self.quote_plus_and_warn(experiment_id)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/start",
            auth=(self.login, self.password),
            json=execution_context,
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
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
        experiment_id = self.quote_plus_and_warn(experiment_id)
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}",
            auth=(self.login, self.password),
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
        )
        if result_data.status_code != 200:
            raise RemoteClientException(
                "Failed to get experiment status. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )

        result: ExperimentExecutionInformationRepresentation = result_data.json()
        return ExperimentExecutionInformation.from_json(result)

    def cancel_experiment(
        self,
        experiment_id: str,
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        experiment_id = self.quote_plus_and_warn(experiment_id)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/cancel",
            auth=(self.login, self.password),
            json=cancellation_context,
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to cancel experiment execution. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def cancel_executors(
        self,
        executors: Iterable[str],
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/executors/cancel",
            auth=(self.login, self.password),
            json={
                "executors": list(executors),
                "cancellation_context": cancellation_context,
            },
            headers={
                "netunicorn-authentication-context": json.dumps(
                    self.authentication_context
                )
            },
        )
        if result.status_code == 200:
            return str(result.json())

        raise RemoteClientException(
            "Failed to cancel provided executors. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def get_flag_values(self, experiment_id: str, flag_name: str) -> FlagValues:
        experiment_id = self.quote_plus_and_warn(experiment_id)
        flag_name = self.quote_plus_and_warn(flag_name)
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/flag/{flag_name}",
            auth=(self.login, self.password),
        )
        if result_data.status_code >= 400:
            raise RemoteClientException(
                "Failed to get flag value. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )

        return FlagValues(**(result_data.json()))

    def set_flag_values(
        self, experiment_id: str, flag_name: str, flag_values: FlagValues
    ) -> None:
        experiment_id = self.quote_plus_and_warn(experiment_id)
        flag_name = self.quote_plus_and_warn(flag_name)
        if flag_values.int_value is None and flag_values.text_value is None:
            raise RemoteClientException(
                "One of int_value or text_value must be provided."
            )

        result_data = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/flag/{flag_name}",
            auth=(self.login, self.password),
            json=flag_values.dict(),
        )
        if result_data.status_code >= 400:
            raise RemoteClientException(
                "Failed to set flag value. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )
