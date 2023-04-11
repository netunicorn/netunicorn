import json
from typing import Dict, List, Literal, Optional, TypeAlias, TypedDict, Union

import uvicorn
from fastapi import FastAPI, Header, HTTPException
from fastapi.openapi.models import Response
from netunicorn.base.deployment import Deployment
from netunicorn.base.nodes import CountableNodePool, Node
from netunicorn.base.types import DeploymentRepresentation, NodeRepresentation
from netunicorn.base.utils import UnicornEncoder
from pydantic import BaseModel

OperationContext: TypeAlias = Optional[str]


class StopExecutorRequest(TypedDict):
    executor_id: str
    node_name: str


class ResultData(TypedDict):
    type: Literal["success", "failure"]
    data: Optional[str]


app = FastAPI()


class HealthResponse(BaseModel):
    status: str


class Results(BaseModel):
    __root__: Dict[str, Optional[str]]


# using original types from netunicorn.base.types introduce recursion during type inference from pydantic
class NodesRepresentation(BaseModel):
    node_pool_type: str
    node_pool_data: List[Union[NodeRepresentation, "NodesRepresentation"]]


async def parse_context(json_str: Optional[str]) -> Optional[dict[str, str]]:
    if not json_str or json_str == "null":
        return None
    try:
        return json.loads(json_str)  # type: ignore
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't parse the context: {e}",
        )


@app.post("/initialize", status_code=204)
async def init() -> None:
    return None


@app.get("/health", status_code=200, responses={500: {"model": HealthResponse}})
async def health() -> HealthResponse:
    return HealthResponse(status="OK")


@app.post("/shutdown", status_code=204)
async def shutdown() -> None:
    return None


@app.post("/deploy/{username}/{experiment_id}", status_code=200)
async def deploy(
    username: str,
    experiment_id: str,
    deployments_data: List[DeploymentRepresentation],
    netunicorn_auth_context: OperationContext = Header(default=None),
    netunicorn_deployment_context: OperationContext = Header(default=None),
) -> Dict[str, ResultData]:
    _ = await parse_context(netunicorn_auth_context)
    _ = await parse_context(netunicorn_deployment_context)
    deployments = [Deployment.from_json(x) for x in deployments_data]
    return {
        x.executor_id: {
            "type": "success",
            "data": "something",
        }
        for x in deployments
    }


@app.post("/execute/{username}/{experiment_id}", status_code=200)
async def execute(
    username: str,
    experiment_id: str,
    deployments_data: List[DeploymentRepresentation],
    netunicorn_auth_context: OperationContext = Header(default=None),
    netunicorn_execution_context: OperationContext = Header(default=None),
) -> Dict[str, ResultData]:
    _ = await parse_context(netunicorn_auth_context)
    _ = await parse_context(netunicorn_execution_context)
    deployments = [Deployment.from_json(x) for x in deployments_data]
    return {
        x.executor_id: {
            "type": "success",
            "data": "something",
        }
        for x in deployments
    }


@app.post("/stop_executors/{username}", status_code=200)
async def stop_executors(
    username: str,
    requests_list: List[StopExecutorRequest],
    netunicorn_auth_context: OperationContext = Header(default=None),
    netunicorn_cancellation_context: OperationContext = Header(default=None),
) -> Dict[str, ResultData]:
    _ = await parse_context(netunicorn_auth_context)
    _ = await parse_context(netunicorn_cancellation_context)
    return {
        x["executor_id"]: {
            "type": "success",
            "data": "something",
        }
        for x in requests_list
    }


@app.get("/nodes/{username}", status_code=200)
async def return_nodes(
    username: str,
    netunicorn_auth_context: OperationContext = Header(default=None),
) -> NodesRepresentation:
    _ = await parse_context(netunicorn_auth_context)
    dummy_nodes = [
        Node(name="node1", properties={"a": 1}),
        Node(name="node2", properties={"b": 2}),
    ]
    dummy_node_pool = CountableNodePool(nodes=dummy_nodes)  # type: ignore

    # or use json.dumps(x, cls=UnicornEncoder)
    json_str = json.dumps(dummy_node_pool, cls=UnicornEncoder)
    return Response(media_type="application/json", content=json_str)  # type: ignore


uvicorn.run(app)
