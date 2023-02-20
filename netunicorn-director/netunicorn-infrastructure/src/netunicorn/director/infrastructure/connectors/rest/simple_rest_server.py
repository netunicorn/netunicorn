import json
from typing import List, Optional, Dict, Union, TypedDict

import uvicorn
from fastapi import FastAPI
from fastapi.openapi.models import Response
from pydantic import BaseModel
from netunicorn.base.utils import UnicornEncoder
from netunicorn.base.types import NodeRepresentation, DeploymentRepresentation
from netunicorn.base.nodes import CountableNodePool, Node
from netunicorn.base.deployment import Deployment


class StopExecutorRequest(TypedDict):
    executor_id: str
    node_name: str


app = FastAPI()


class HealthResponse(BaseModel):
    status: str


class Results(BaseModel):
    __root__: Dict[str, Optional[str]]


# using original types from netunicorn.base.types introduce recursion during type inference from pydantic
class NodesRepresentation(BaseModel):
    node_pool_type: str
    node_pool_data: List[Union[NodeRepresentation, "NodesRepresentation"]]


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
    username: str, experiment_id: str, deployments_data: List[DeploymentRepresentation]
) -> Dict[str, Optional[str]]:
    deployments = [Deployment.from_json(x) for x in deployments_data]

    # dict values: None if successful, error message otherwise
    results: Dict[str, Optional[str]] = {x.executor_id: "meh" for x in deployments}
    return results


@app.post("/execute/{username}/{experiment_id}", status_code=200)
async def execute(
    username: str, experiment_id: str, deployments_data: List[DeploymentRepresentation]
) -> Dict[str, Optional[str]]:
    deployments = [Deployment.from_json(x) for x in deployments_data]

    # dict values: None if successful, error message otherwise
    results: Dict[str, Optional[str]] = {x.executor_id: "meh" for x in deployments}
    return results


@app.post("/stop_executors/{username}", status_code=200)
async def stop_executors(
    username: str, requests_list: List[StopExecutorRequest]
) -> Dict[str, Optional[str]]:
    # dict values: None if successful, error message otherwise
    results: Dict[str, Optional[str]] = {x["executor_id"]: "meh" for x in requests_list}
    return results


@app.get("/nodes/{username}", status_code=200)
async def return_nodes(username: str) -> NodesRepresentation:
    dummy_nodes = [
        Node(name="node1", properties={"a": 1}),
        Node(name="node2", properties={"b": 2}),
    ]
    dummy_node_pool = CountableNodePool(nodes=dummy_nodes)

    # or use json.dumps(x, cls=UnicornEncoder)
    json_str = json.dumps(dummy_node_pool, cls=UnicornEncoder)
    return Response(media_type="application/json", content=json_str)  # type: ignore


uvicorn.run(app)
