from __future__ import annotations

from abc import abstractmethod
from logging import Logger
from typing import Any, Optional, Protocol, Tuple

from netunicorn.base.deployment import Deployment
from netunicorn.base.nodes import Nodes
from returns.result import Result

from .types import StopExecutorRequest


class NetunicornConnectorProtocol(Protocol):
    """
    Represents netunicorn infrastructure connector protocol.
    All connectors must implement this protocol.
    Connectors provide available node pools of the infrastructure and
    ability to deploy and execute experiments.

    If connector raises an exception during the execution of any method,
    it will be removed from the list of available connectors.

    IMPORTANT: all methods of this class have *args and **kwargs to allow
    adding new parameters without breaking backward compatibility.
    """

    @abstractmethod
    def __init__(
        self,
        connector_name: str,
        configuration: str | None,
        netunicorn_gateway: str,
        logger: Optional[Logger] = None,
        *args: Any,
        **kwargs: Any,
    ):
        """
        Connector constructor.
        :param connector_name: system-wide unique connector name
        :param configuration: connector-specific configuration string (could be path to config file or anything)
        :param netunicorn_gateway: netunicorn gateway endpoint
        """
        _ = connector_name
        _ = configuration
        _ = netunicorn_gateway
        _ = logger

    @abstractmethod
    async def initialize(self, *args: Any, **kwargs: Any) -> None:
        """
        This method is guaranteed to be called immediately after the constructor
        to provide async initialization capabilities.
        If you don't know why you can need this method, leave it empty.
        """
        pass

    @abstractmethod
    async def health(self, *args: Any, **kwargs: Any) -> Tuple[bool, str]:
        """
        Health check of the connector.
        :return: True if connector is healthy, False otherwise, and a description of the health status
        """
        pass

    @abstractmethod
    async def shutdown(self, *args: Any, **kwargs: Any) -> None:
        """
        Shutdown the connector. Will be called in the end of the program.
        """
        pass

    @abstractmethod
    async def get_nodes(
        self,
        username: str,
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Nodes:
        """
        Get available nodes for the user.
        :param username: username
        :param authentication_context: authentication context provided by the user
        :return: Pool of nodes
        """
        pass

    @abstractmethod
    async def deploy(
        self,
        username: str,
        experiment_id: str,
        deployments: list[Deployment],
        deployment_context: Optional[dict[str, str]],
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Result[Optional[str], str]]:
        """
        This method deploys the given list of deployments to the infrastructure.
        See the documentation for available deployment environments for correct deployment implementation.

        :param username: username of the user who deploys the experiment
        :param experiment_id: ID of the experiment
        :param deployments: list of deployments to deploy
        :param deployment_context: optional deployment context provided directly from the user.
        Can be used to pass additional information to the connector, netunicorn does not modify or validate this field.
        You can define in the connector's documentation some additional deployment flags and ask user to set them in this field.
        E.g.: network configuration for virtual deployments (link capacity, etc.)
        :param authentication_context: optional authentication context provided by the user
        :return: dictionary of executor_id
        ((unique, parsed from deployment) -> Result[optional success message, error message])
        """
        pass

    @abstractmethod
    async def execute(
        self,
        username: str,
        experiment_id: str,
        deployments: list[Deployment],
        execution_context: Optional[dict[str, str]],
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Result[Optional[str], str]]:
        """
        This method starts execution of the given list of deployments on the infrastructure.
        Usually, that means that connector should run `python3 -m netunicorn.executor` on the node
         with the next environment variables:
        - NETUNICORN_GATEWAY_ENDPOINT: netunicorn gateway endpoint
        - NETUNICORN_EXECUTOR_ID: unique executor ID
        - NETUNICORN_EXPERIMENT_ID: experiment ID

        :param username: username of the user who deploys the experiment
        :param experiment_id: ID of the experiment
        :param deployments: list of deployments to start execution
        :param execution_context: optional execution context provided directly from the user.
        Can be used to pass additional information to the connector, netunicorn does not modify or validate this field.
        You can define in the connector's documentation some additional deployment flags and ask user to set them in this field.
        :param authentication_context: optional authentication context provided by the user
        :return: dictionary of (executor_id (unique, parsed from deployment) -> Result[optional success message, error message])
        """
        pass

    @abstractmethod
    async def stop_executors(
        self,
        username: str,
        requests_list: list[StopExecutorRequest],
        cancellation_context: Optional[dict[str, str]],
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Result[Optional[str], str]]:
        """
        This method stops execution of the given list of executors on the infrastructure.
        :param username: username of the user
        :param requests_list: list of StopExecutorRequests
        :param cancellation_context: optional cancellation context provided directly from the user.
        User can define arbitrary fields in this dictionary and connector can parse them.
        E.g.: a stopping reason for the experiment, or soft-kill vs hard-kill.
        :param authentication_context: optional authentication context provided by the user
        :return: dictionary of executor_id (unique, parsed from deployment) -> Result[optional success message, error message]
        """
        pass

    @abstractmethod
    async def cleanup(
        self,
        experiment_id: str,
        deployments: list[Deployment],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        This method is called after the experiment is finished.
        It is used to clean up the infrastructure after the experiment.
        E.g., delete Docker containers, images, etc.
        Experiment is always marked as cleaned up, even if this method fails,
        and this method should not return any result.

        :param experiment_id: ID of the experiment
        :param deployments: list of deployments to use for cleanup
        :return: None
        """
        pass
