"""
Various auxiliary types.
"""

from __future__ import annotations

import sys
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel
from returns.result import Result
from typing_extensions import TypedDict

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

NodeProperty = Union[str, float, int, Set[str], None]

TaskElementResult: TypeAlias = Result[Any, Any]
ExecutionGraphResult = Dict[str, List[TaskElementResult]]
PipelineResult = ExecutionGraphResult


class NodeRepresentation(TypedDict):
    """
    Node JSON representation.
    """

    name: str
    """
    Node name.
    """

    properties: Dict[str, NodeProperty]
    """
    Node properties.
    """

    additional_properties: Dict[str, NodeProperty]
    """
    Internal node properties.
    """

    architecture: str
    """
    Node architecture.
    """


class EnvironmentDefinitionRepresentation(TypedDict):
    """
    Environment definition JSON representation.
    """

    commands: List[str]
    """
    Environment definition commands.
    """

    runtime_context: RuntimeContextRepresentation
    """
    Runtime context JSON representation.
    """


class DeploymentRepresentation(TypedDict):
    """
    Deployment JSON representation.
    """

    node: NodeRepresentation
    """
    Node JSON representation.
    """

    prepared: bool
    """
    Prepared flag.
    """

    executor_id: str
    """
    Executor ID.
    """

    error: Optional[str]
    """
    Error message.
    """

    execution_graph: bytes
    """
    Serialized execution graph.
    """

    keep_alive_timeout_minutes: int
    """
    Keep alive timeout value.
    """

    cleanup: bool
    """
    Cleanup flag.
    """

    environment_definition: EnvironmentDefinitionRepresentation
    """
    Environment definition JSON representation.
    """

    environment_definition_type: str
    """
    Type of environment definition.
    """


class NodesRepresentation(TypedDict):
    """
    Nodes JSON representation.
    """

    node_pool_type: str
    """
    Type of node pool.
    """

    node_pool_data: List[Union[NodeRepresentation, NodesRepresentation]]
    """
    Node pool data.
    """


class BuildContextRepresentation(TypedDict):
    """
    Build context JSON representation.
    """

    python_version: str
    """
    Python version.
    """

    cloudpickle_version: Optional[str]
    """
    Cloudpickle version.
    """


class RuntimeContextRepresentation(TypedDict):
    """
    Runtime context JSON representation.
    """

    ports_mapping: Dict[int, int]
    """
    Ports mapping dictionary.
    """

    environment_variables: Dict[str, str]
    """
    Environment variables dictionary.
    """

    additional_arguments: List[str]
    """
    Additional arguments list.
    """


class ShellExecutionRepresentation(EnvironmentDefinitionRepresentation):
    """
    Shell execution Environment definition JSON representation.
    """

    pass


class DockerImageRepresentation(EnvironmentDefinitionRepresentation):
    """
    Docker image Environment definition JSON representation.
    """

    image: Optional[str]
    """
    Image name.
    """

    build_context: BuildContextRepresentation
    """
    Build context JSON representation.
    """


class ExperimentRepresentation(TypedDict):
    """
    Experiment JSON representation.
    """

    deployment_map: List[DeploymentRepresentation]
    """
    List of deployments of the experiment.
    """

    deployment_context: Optional[Dict[str, Dict[str, str]]]
    """
    Deployment context.
    """


class DeploymentExecutionResultRepresentation(TypedDict):
    """
    Deployment execution result JSON representation.
    """

    node: NodeRepresentation
    """
    Node JSON representation.
    """

    execution_graph: str
    """
    Serialized execution_graph.
    """

    result: Optional[str]
    """
    Result of execution.
    """

    error: Optional[str]
    """
    Error message.
    """


class ExperimentExecutionInformationRepresentation(TypedDict):
    """
    Experiment execution information JSON representation.
    """

    status: int
    """
    Status of execution value (see ExperimentExecutionStatus).
    """

    experiment: Optional[ExperimentRepresentation]
    """
    Experiment definition.
    """

    execution_result: Union[None, str, List[DeploymentExecutionResultRepresentation]]
    """
    Execution result.
    """


class ExecutorState(IntEnum):
    """
    Executor state.
    """

    LOOKING_FOR_EXECUTION_GRAPH = 0
    """
    Looking for the execution graph locally or downloading from netunicorn gateway.
    """

    EXECUTING = 1
    """
    Currently executing the graph.
    """

    REPORTING = 2
    """
    Execution is finished and executor is reporting results.
    """

    FINISHED = 3
    """
    Execution is finished and results are reported (if needed).
    """


class FlagValues(BaseModel):
    """
    | Flag values for experiment-wide flags. These flags could be get and set by the user or any executor.
    | One can use these flags to synchronize different executors, pass additional information,
        or manually control the experiment.
    |
    | Flag value could contain text, integer, or both. Integer values could be atomically incremented or decremented.
    """

    text_value: Optional[str] = None
    """
    Text value of the flag.
    """

    int_value: int = 0
    """
    Integer value of the flag.
    """
