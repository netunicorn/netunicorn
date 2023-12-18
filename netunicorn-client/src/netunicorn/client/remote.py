"""
Default remote client for netunicorn.
"""
import json
import warnings
from functools import wraps
from typing import Dict, Iterable, Optional, Callable, Any
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
from requests import PreparedRequest
from requests.auth import AuthBase

from .base import BaseClient


class OAuth2Bearer(AuthBase):
    def __init__(self, token: str):
        self.token = token

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        r.headers["authorization"] = "Bearer " + self.token
        return r


class RemoteClientException(Exception):
    """
    Generic exception for remote client.
    """

    pass


def authenticated(function: Callable) -> Callable:
    @wraps(function)
    def wrapper(self: "RemoteClient", *args, **kwargs) -> Any:
        if not self._verify_token():
            self._perform_authentication()
        return function(self, *args, **kwargs)

    return wrapper


class RemoteClient(BaseClient):
    """
    Remote client for Unicorn.

    :param endpoint: netunicorn endpoint
    :param login: netunicorn login
    :param password: netunicorn password
    :param authentication_context: authentication context for connectors
    """

    def __init__(
        self,
        endpoint: str,
        login: str,
        password: str,
        authentication_context: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        self.endpoint = endpoint
        """
        netunicorn installation endpoint.
        """

        self.login = login
        """
        netunicorn user login.
        """

        self.password = password
        """
        netunicorn user password.
        """

        self.authentication_context = authentication_context or {}
        """
        Authentication context for connectors.
            E.g., if a connector requires users to provide additional security tokens, it could be specified here.
            Format: {connector_name: {key: value}}
        """

        self._session_token: Optional[str] = None

    @staticmethod
    def _quote_plus_and_warn(string: str) -> str:
        result = quote_plus(string)
        if result != string:
            warnings.warn(
                f"String {string} was encoded to {result}. "
                f"Consider using only alphanumeric characters and underscores."
            )

        return result

    def _perform_authentication(self) -> None:
        result = req.post(
            f"{self.endpoint}/api/v1/token",
            data={"username": self.login, "password": self.password},
        )
        if result.status_code == 200:
            self._session_token = result.json()["access_token"]
            return

        raise RemoteClientException(
            f"Failed to authenticate. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    def _verify_token(self) -> bool:
        if self._session_token is None:
            return False

        result = req.get(
            f"{self.endpoint}/api/v1/verify_token",
            auth=OAuth2Bearer(self._session_token),
        )
        return result.status_code == 200

    @authenticated
    def healthcheck(self) -> bool:
        result = req.get(
            f"{self.endpoint}/api/v1/health", auth=OAuth2Bearer(self._session_token)
        )
        if result.status_code == 200:
            return True

        raise RemoteClientException(
            f"The backend is not in healthy state. "
            f"Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
        )

    @authenticated
    def get_nodes(self) -> Nodes:
        result = req.get(
            f"{self.endpoint}/api/v1/nodes",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def delete_experiment(self, experiment_name: str) -> None:
        experiment_name = self._quote_plus_and_warn(experiment_name)
        result_data = req.delete(
            f"{self.endpoint}/api/v1/experiment/{experiment_name}",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def get_experiments(self) -> Dict[str, ExperimentExecutionInformation]:
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
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

        experiment_id = self._quote_plus_and_warn(experiment_id)
        data = json.dumps(experiment, cls=UnicornEncoder)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/prepare",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def start_execution(
        self,
        experiment_id: str,
        execution_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        experiment_id = self._quote_plus_and_warn(experiment_id)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/start",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def get_experiment_status(
        self, experiment_id: str
    ) -> ExperimentExecutionInformation:
        experiment_id = self._quote_plus_and_warn(experiment_id)
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def cancel_experiment(
        self,
        experiment_id: str,
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        experiment_id = self._quote_plus_and_warn(experiment_id)
        result = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/cancel",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def cancel_executors(
        self,
        executors: Iterable[str],
        cancellation_context: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
        result = req.post(
            f"{self.endpoint}/api/v1/executors/cancel",
            auth=OAuth2Bearer(self._session_token),
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

    @authenticated
    def get_flag_values(self, experiment_id: str, flag_name: str) -> FlagValues:
        experiment_id = self._quote_plus_and_warn(experiment_id)
        flag_name = self._quote_plus_and_warn(flag_name)
        result_data = req.get(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/flag/{flag_name}",
            auth=OAuth2Bearer(self._session_token),
        )
        if result_data.status_code >= 400:
            raise RemoteClientException(
                "Failed to get flag value. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )

        return FlagValues(**(result_data.json()))

    @authenticated
    def set_flag_values(
        self, experiment_id: str, flag_name: str, flag_values: FlagValues
    ) -> None:
        experiment_id = self._quote_plus_and_warn(experiment_id)
        flag_name = self._quote_plus_and_warn(flag_name)
        if flag_values.int_value is None and flag_values.text_value is None:
            raise RemoteClientException(
                "One of int_value or text_value must be provided."
            )

        result_data = req.post(
            f"{self.endpoint}/api/v1/experiment/{experiment_id}/flag/{flag_name}",
            auth=OAuth2Bearer(self._session_token),
            json=flag_values.model_dump(),
        )
        if result_data.status_code >= 400:
            raise RemoteClientException(
                "Failed to set flag value. "
                f"Status code: {result_data.status_code}, content: {result_data.content.decode('utf-8')}"
            )
