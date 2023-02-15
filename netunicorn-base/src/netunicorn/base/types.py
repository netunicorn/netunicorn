from __future__ import annotations
import sys

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict

from typing import Dict, Set, Union, List, Optional

NodeProperty = Union[str, float, int, Set[str], None]


class DeploymentRepresentation(TypedDict):
    node: NodeRepresentation
    prepared: bool
    executor_id: str
    error: Optional[str]
    pipeline: bytes
    keep_alive_timeout_minutes: int
    environment_definition: EnvironmentDefinitionRepresentation
    environment_definition_type: str


class NodeRepresentation(TypedDict):
    name: str
    properties: Dict[str, NodeProperty]
    additional_properties: Dict[str, NodeProperty]
    architecture: str


class NodesRepresentation(TypedDict):
    node_pool_type: str
    node_pool_data: List[Union[NodeRepresentation, NodesRepresentation]]


class RuntimeContextRepresentation(TypedDict):
    ports_mapping: Dict[int, int]
    environment_variables: Dict[str, str]
    additional_arguments: List[str]


class EnvironmentDefinitionRepresentation(TypedDict):
    commands: List[str]


class ShellExecutionRepresentation(EnvironmentDefinitionRepresentation):
    runtime_context: RuntimeContextRepresentation


class DockerImageRepresentation(EnvironmentDefinitionRepresentation):
    image: Optional[str]
    build_context: BuildContextRepresentation
    runtime_context: RuntimeContextRepresentation


class BuildContextRepresentation(TypedDict):
    python_version: str
    cloudpickle_version: Optional[str]


class ExperimentRepresentation(TypedDict):
    deployment_map: List[DeploymentRepresentation]


class DeploymentExecutionResultRepresentation(TypedDict):
    node: NodeRepresentation
    pipeline: str
    result: Optional[str]
    error: Optional[str]


class ExperimentExecutionInformationRepresentation(TypedDict):
    status: int
    experiment: Optional[ExperimentRepresentation]
    execution_result: Union[None, str, List[DeploymentExecutionResultRepresentation]]
