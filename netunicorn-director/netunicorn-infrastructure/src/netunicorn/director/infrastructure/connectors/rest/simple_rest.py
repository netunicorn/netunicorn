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
    """
    Config is a valid JSON-serialized object with the next properties:
    - url: str
    - api_key: str
    - init_params: dict[str, str]

    `url` is a URL of the REST API endpoint.
    `api_key` is a string that will be used as for authentication and should match the API key of the REST API endpoint
    (usually, NETUNICORN_API_KEY environment variable).
    `init_params` is a dictionary that will be passed to the REST API endpoint during initialization. Generally, connectors
    use these parameters to configure the underlying infrastructure. Optional.
    """
    def __init__(
        self,
        connector_name: str,
        config: str | None,
        netunicorn_gateway: str,
        logger: Optional[logging.Logger] = None,
    ):
        if config is None:
            raise ValueError("At least `url` and `api_key` are required for REST connector")

        if not logger:
            logging.basicConfig()
            logger = logging.getLogger(__name__)
        self.logger = logger
        self.connector_name = connector_name
        self.config = config
        self.netunicorn_gateway = netunicorn_gateway

        parsed_config = json.loads(config)
        if ('url' not in parsed_config) or ('api_key' not in parsed_config):
            raise ValueError("At least `url` and `api_key` are required for REST connector")
        self.url = parsed_config['url']
        self.api_key = parsed_config['api_key']
        self.init_params = parsed_config.get('init_params', {})

    async def initialize(self, *args, **kwargs) -> None:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60,
        ) as session:
            async with session.post(
                    f"{self.url}/initialize",
                    json=self.init_params,
            ) as response:
                if not response.ok:
                    raise ValueError(f"Failed to initialize connector: {response.content}")

    async def health(self) -> Tuple[bool, str]:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as session:
            async with session.get(f"{self.url}/health") as response:
                status = response.ok
                message = (await response.json())["status"]
                return status, message

    async def shutdown(self) -> None:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as session:
            async with session.post(f"{self.url}/shutdown") as response:
                if not response.ok:
                    raise ValueError(f"Failed to shutdown connector: {response.content}")

    async def get_nodes(
        self,
        username: str,
        authentication_context: Optional[dict[str, str]] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Nodes:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        ) as session:
            async with session.get(
                f"{self.url}/nodes/{username}",
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context,
                        cls=UnicornEncoder,
                    )
                },
            ) as response:
                if not response.ok:
                    raise ValueError(f"Failed to get nodes: {response.content}")
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
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        ) as session:
            async with session.post(
                f"{self.url}/deploy/{username}/{experiment_id}",
                json=deployments,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context,
                        cls=UnicornEncoder,
                    ),
                    "netunicorn-deployment-context": json.dumps(deployment_context, cls=UnicornEncoder),
                },
            ) as response:
                if not response.ok:
                    self.logger.error({"deployments": deployments, "deployment-context": deployment_context})
                    raise ValueError(f"Failed to deploy: {response.content}")
                result = await response.json()
                self.logger.debug(result)
                return {
                    x: Success(y["result"])
                    if y["result_type"].lower() == "success"
                    else Failure(y["result"])
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
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
        ) as session:
            async with session.post(
                f"{self.url}/execute/{username}/{experiment_id}",
                json=deployments,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context,
                        cls=UnicornEncoder,
                    ),
                    "netunicorn-execution-context": json.dumps(execution_context, cls=UnicornEncoder),
                },
            ) as response:
                if not response.ok:
                    self.logger.error({"deployments": deployments, "execution-context": execution_context})
                    raise ValueError(f"Failed to execute: {response.content}")
                result = await response.json()
                return {
                    x: Success(y["result"])
                    if y["result_type"].lower() == "success"
                    else Failure(y["result"])
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
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        ) as session:
            async with session.post(
                f"{self.url}/stop_executors/{username}",
                json=requests_list,
                headers={
                    "netunicorn-authentication-context": json.dumps(
                        authentication_context,
                        cls=UnicornEncoder,
                    ),
                    "netunicorn-cancellation-context": json.dumps(cancellation_context, cls=UnicornEncoder),
                },
            ) as response:
                if not response.ok:
                    self.logger.error({"requests": requests_list, "cancellation-context": cancellation_context})
                    raise ValueError(f"Failed to stop executors: {response.content}")
                result = await response.json()
                return {
                    x: Success(y["result"])
                    if y["result_type"].lower() == "success"
                    else Failure(y["result"])
                    for x, y in result.items()
                }

    async def cleanup(
            self,
            experiment_id: str,
            deployments: list[Deployment],
            *args: Any,
            **kwargs: Any
    ) -> None:
        async with aiohttp.ClientSession(
            json_serialize=lambda x: json.dumps(x, cls=UnicornEncoder),
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=300,
        ) as session:
            async with session.post(
                f"{self.url}/cleanup/{experiment_id}",
                json=deployments,
            ) as response:
                if not response.ok:
                    self.logger.error({"deployments": deployments})
                    raise ValueError(f"Failed to cleanup: {response.content}")
