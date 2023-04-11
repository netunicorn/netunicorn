from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from netunicorn.base.deployment import Deployment
from netunicorn.base.nodes import CountableNodePool, Node, Nodes
from netunicorn.director.base.connectors.protocol import NetunicornConnectorProtocol
from netunicorn.director.base.connectors.types import StopExecutorRequest
from returns.result import Result, Success


class DummyNetunicornConnector(NetunicornConnectorProtocol):
    def __init__(
        self,
        connector_name: str,
        config_file: str | None,
        netunicorn_gateway: str,
        logger: Optional[logging.Logger] = None,
    ):
        if not logger:
            logging.basicConfig()
            logger = logging.getLogger(__name__)
        self.logger = logger
        self.logger.info(
            f"I'm a dummy connector {connector_name}! I don't do anything! :("
        )
        self.logger.info(
            f"I've been provided with config file {config_file} and netunicorn gateway {netunicorn_gateway}!"
        )

    async def initialize(self) -> None:
        self.logger.info("Initialize called")
        pass

    async def health(self) -> Tuple[bool, str]:
        return True, "I'm always healthy!"

    async def shutdown(self) -> None:
        self.logger.info("Shutdown called")

    async def get_nodes(
        self,
        username: str,
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Nodes:
        self.logger.info(f"Get nodes called with {username=}")
        self.logger.info(f"Authentication context: {authentication_context=}")
        self.logger.info(f"Additional args: {args=}, {kwargs=}")
        self.logger.info("Returning dummy node pool")
        return CountableNodePool(nodes=[Node(name="dummy", properties={})])

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
        self.logger.info(
            f"Deploy called with {username=}, {experiment_id=}, {deployments=}, {deployment_context=},"
            f" {authentication_context=}, {args=}, {kwargs=}"
        )
        self.logger.info("Returning dummy deployment results")
        return {deployment.executor_id: Success(None) for deployment in deployments}

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
        self.logger.info(
            f"Execute called with {username=}, {experiment_id=}, {deployments=}, {execution_context=},"
            f" {authentication_context=}, {args=}, {kwargs=}"
        )
        self.logger.info("Returning dummy execution results")
        return {deployment.executor_id: Success(None) for deployment in deployments}

    async def stop_executors(
        self,
        username: str,
        requests_list: list[StopExecutorRequest],
        cancellation_context: Optional[dict[str, str]],
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Result[Optional[str], str]]:
        self.logger.info(
            f"Stop executors called with {username=}, {requests_list=}, {cancellation_context=},"
            f" {authentication_context=}, {args=}, {kwargs=}"
        )
        self.logger.info("Returning dummy stop executors results")
        return {request["executor_id"]: Success(None) for request in requests_list}
