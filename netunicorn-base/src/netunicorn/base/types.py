from __future__ import annotations

import sys
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set, TypedDict, Union

from pydantic import BaseModel
from returns.result import Result

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

NodeProperty = Union[str, float, int, Set[str], None]

TaskElementResult: TypeAlias = Result[Any, Any]
PipelineResult = Dict[str, List[TaskElementResult]]


class NodeRepresentation(TypedDict):
    name: str
    properties: Dict[str, NodeProperty]
    additional_properties: Dict[str, NodeProperty]
    architecture: str


class EnvironmentDefinitionRepresentation(TypedDict):
    commands: List[str]


class DeploymentRepresentation(TypedDict):
    node: NodeRepresentation
    prepared: bool
    executor_id: str
    error: Optional[str]
    pipeline: bytes
    keep_alive_timeout_minutes: int
    cleanup: bool
    environment_definition: EnvironmentDefinitionRepresentation
    environment_definition_type: str


class NodesRepresentation(TypedDict):
    node_pool_type: str
    node_pool_data: List[Union[NodeRepresentation, NodesRepresentation]]


class BuildContextRepresentation(TypedDict):
    python_version: str
    cloudpickle_version: Optional[str]


class RuntimeContextRepresentation(TypedDict):
    ports_mapping: Dict[int, int]
    environment_variables: Dict[str, str]
    additional_arguments: List[str]


class ShellExecutionRepresentation(EnvironmentDefinitionRepresentation):
    runtime_context: RuntimeContextRepresentation


class DockerImageRepresentation(EnvironmentDefinitionRepresentation):
    image: Optional[str]
    build_context: BuildContextRepresentation
    runtime_context: RuntimeContextRepresentation


class ExperimentRepresentation(TypedDict):
    deployment_map: List[DeploymentRepresentation]
    deployment_context: Optional[Dict[str, Dict[str, str]]]


class DeploymentExecutionResultRepresentation(TypedDict):
    node: NodeRepresentation
    pipeline: str
    result: Optional[str]
    error: Optional[str]


class ExperimentExecutionInformationRepresentation(TypedDict):
    status: int
    experiment: Optional[ExperimentRepresentation]
    execution_result: Union[None, str, List[DeploymentExecutionResultRepresentation]]


class PipelineExecutorState(IntEnum):
    LOOKING_FOR_PIPELINE = 0
    EXECUTING = 1
    REPORTING = 2
    FINISHED = 3


class FlagValues(BaseModel):
    text_value: Optional[str] = None
    int_value: int = 0
