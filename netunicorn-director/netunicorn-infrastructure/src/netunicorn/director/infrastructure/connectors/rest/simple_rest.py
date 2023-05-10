from __future__ import annotations

import json
import logging
from typing import Any, Optional, Tuple

import aiohttp
from netunicorn.base.deployment import Deployment
from netunicorn.base.nodes import Nodes
from netunicorn.base.utils import UnicornEncoder
from netunicorn.director.base.connectors.protocol import NetunicornConnectorProtocol
from netunicorn.director.base.connectors.types import StopExecutorRequest
from returns.result import Failure, Result, Success


class SimpleRESTConnector(NetunicornConnectorProtocol):
    def __init__(
        self,
        connector_name: str,
        url: str | None,
        netunicorn_gateway: str,
        logger: Optional[logging.Logger] = None,
    ):
        if url is None:
            raise ValueError("URL is required for REST connector")

        if not logger:
            logging.basicConfig()
            logger = logging.getLogger(__name__)
        self.logger = logger
        self.connector_name = connector_name
        self.url = url.removesuffix("/")
        self.netunicorn_gateway = netunicorn_gateway

    async def initialize(self) -> None:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(f"{self.url}/initialize") as response:
                response.raise_for_status()

    async def health(self) -> Tuple[bool, str]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.get(f"{self.url}/health") as response:
                response.raise_for_status()
                status = response.ok
                message = (await response.json())["status"]
                return status, message

    async def shutdown(self) -> None:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(f"{self.url}/shutdown") as response:
                response.raise_for_status()

    async def get_nodes(
        self,
        username: str,
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Nodes:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.get(
                f"{self.url}/nodes/{username}",
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context
                    )
                },
            ) as response:
                response.raise_for_status()
                nodes = await response.json()
                return Nodes.dispatch_and_deserialize(nodes)

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
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/deploy/{username}/{experiment_id}",
                json=deployments,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context
                    ),
                    "netunicorn-deployment-context": json.dumps(deployment_context),
                },
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(y["data"])
                    if y["type"] == "success"
                    else Failure(y["data"])
                    for x, y in result.items()
                }

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
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/execute/{username}/{experiment_id}",
                json=deployments,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context
                    ),
                    "netunicorn-execution-context": json.dumps(execution_context),
                },
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(y["data"])
                    if y["type"] == "success"
                    else Failure(y["data"])
                    for x, y in result.items()
                }

    async def stop_executors(
        self,
        username: str,
        requests_list: list[StopExecutorRequest],
        cancellation_context: Optional[dict[str, str]],
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> dict[str, Result[Optional[str], str]]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/stop_executors/{username}",
                json=requests_list,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context
                    ),
                    "netunicorn-cancellation-context": json.dumps(cancellation_context),
                },
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(y["data"])
                    if y["type"] == "success"
                    else Failure(y["data"])
                    for x, y in result.items()
                }
