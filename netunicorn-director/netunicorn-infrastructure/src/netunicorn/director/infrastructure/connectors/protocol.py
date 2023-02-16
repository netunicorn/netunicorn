from __future__ import annotations

from abc import abstractmethod
from logging import Logger
from typing import Protocol, Optional, Tuple

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
    """

    @abstractmethod
    def __init__(
        self,
        connector_name: str,
        configuration: str | None,
        netunicorn_gateway: str,
        logger: Optional[Logger] = None,
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
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """
        This method is guaranteed to be called immediately after the constructor
        to provide async initialization capabilities.
        If you don't know why you can need this method, leave it empty.
        """
        pass

    @abstractmethod
    async def health(self) -> Tuple[bool, str]:
        """
        Health check of the connector.
        :return: True if connector is healthy, False otherwise, and a description of the health status
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Shutdown the connector. Will be called in the end of the program.
        """
        pass

    @abstractmethod
    async def get_nodes(self, username: str) -> Nodes:
        """
        Get available nodes for the user.
        :param username: username
        :return: Pool of nodes
        """
        pass

    @abstractmethod
    async def deploy(
        self, username: str, experiment_id: str, deployments: list[Deployment]
    ) -> dict[str, Result[None, str]]:
        """
        This method deploys the given list of deployments to the infrastructure.
        See the documentation for available deployment environments for correct deployment implementation.

        :param username: username of the user who deploys the experiment
        :param experiment_id: ID of the experiment
        :param deployments: list of deployments to deploy
        :return: dictionary of executor_id (unique, parsed from deployment) -> Result[None, error message]
        """
        pass

    @abstractmethod
    async def execute(
        self, username: str, experiment_id: str, deployments: list[Deployment]
    ) -> dict[str, Result[None, str]]:
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
        :return: dictionary of executor_id (unique, parsed from deployment) -> Result[None, error message]
        """
        pass

    @abstractmethod
    async def stop_executors(
        self, username: str, requests_list: list[StopExecutorRequest]
    ) -> dict[str, Result[None, str]]:
        """
        This method stops execution of the given list of executors on the infrastructure.
        :param username: username of the user
        :param requests_list: list of StopExecutorRequests
        :return: dictionary of executor_id (unique, parsed from deployment) -> Result[None, error message]
        """
        pass
