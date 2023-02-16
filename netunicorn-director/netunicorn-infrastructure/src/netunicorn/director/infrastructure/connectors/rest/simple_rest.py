from __future__ import annotations

import json
import logging
import aiohttp

from typing import Optional, Tuple

from netunicorn.base.deployment import Deployment
from netunicorn.base.nodes import Nodes
from netunicorn.director.base.utils import UnicornEncoder
from returns.result import Result, Success, Failure

from ..protocol import NetunicornConnectorProtocol
from ..types import StopExecutorRequest


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

    async def get_nodes(self, username: str) -> Nodes:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.get(f"{self.url}/nodes/{username}") as response:
                response.raise_for_status()
                nodes = await response.json()
                return Nodes.dispatch_and_deserialize(nodes)

    async def deploy(
        self, username: str, experiment_id: str, deployments: list[Deployment]
    ) -> dict[str, Result[None, str]]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/deploy/{username}/{experiment_id}", json=deployments
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(None) if y is None else Failure(y)
                    for x, y in result.items()
                }

    async def execute(
        self, username: str, experiment_id: str, deployments: list[Deployment]
    ) -> dict[str, Result[None, str]]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/execute/{username}/{experiment_id}", json=deployments
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(None) if y is None else Failure(y)
                    for x, y in result.items()
                }

    async def stop_executors(
        self, username: str, requests_list: list[StopExecutorRequest]
    ) -> dict[str, Result[None, str]]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder)
        ) as session:
            async with session.post(
                f"{self.url}/stop_executors/{username}", json=requests_list
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return {
                    x: Success(None) if y is None else Failure(y)
                    for x, y in result.items()
                }
