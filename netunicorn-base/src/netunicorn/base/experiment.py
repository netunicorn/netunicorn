from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union

from returns.result import Result

from .deployment import Deployment
from .nodes import Node, Nodes
from .pipeline import Pipeline
from .types import (
    DeploymentExecutionResultRepresentation,
    ExperimentExecutionInformationRepresentation,
    ExperimentRepresentation,
    PipelineResult,
)
from .utils import LogType


class ExperimentStatus(Enum):
    UNKNOWN = 0
    PREPARING = 1
    READY = 2
    RUNNING = 3
    FINISHED = 4

    def __json__(self) -> int:
        return self.value

    @classmethod
    def from_json(cls, value: int) -> ExperimentStatus:
        return cls(value)


class Experiment:
    def __init__(
        self, deployment_context: Optional[Dict[str, Dict[str, str]]] = None
    ) -> None:
        self.deployment_map: List[Deployment] = []
        self.deployment_context = deployment_context

    def append(self, node: Node, pipeline: Pipeline) -> Experiment:
        self.deployment_map.append(Deployment(node, pipeline))
        return self

    def map(self, pipeline: Pipeline, nodes: Sequence[Node]) -> Experiment:
        if isinstance(nodes, Nodes):
            raise TypeError("Expected sequence of nodes, got Nodes instead")

        for node in nodes:
            if not isinstance(node, Node):
                raise TypeError(f"Expected sequence of nodes, got {type(node)} instead")
            self.append(node, pipeline)
        return self

    def __json__(self) -> ExperimentRepresentation:
        return {
            "deployment_map": [x.__json__() for x in self.deployment_map],
            "deployment_context": self.deployment_context,
        }

    @classmethod
    def from_json(cls, data: ExperimentRepresentation) -> Experiment:
        instance = cls.__new__(cls)
        instance.deployment_map = [
            Deployment.from_json(x) for x in data["deployment_map"]
        ]
        instance.deployment_context = data.get("deployment_context")
        return instance

    def __getitem__(self, item: int) -> Deployment:
        return self.deployment_map[item]

    def __iter__(self) -> Iterator[Deployment]:
        return iter(self.deployment_map)

    def __len__(self) -> int:
        return len(self.deployment_map)

    def __str__(self) -> str:
        return "; ".join([f"<{x}>" for x in self.deployment_map])

    def __repr__(self) -> str:
        return str(self)

    def __add__(self, other: Experiment) -> Experiment:
        new_map = copy.deepcopy(self)
        new_map.deployment_map.extend(other.deployment_map)
        if other.deployment_context:
            if new_map.deployment_context is None:
                new_map.deployment_context = {}
            new_map.deployment_context.update(other.deployment_context)
        return new_map


class DeploymentExecutionResult:
    def __init__(
        self,
        node: Node,
        serialized_pipeline: bytes,
        result: Optional[bytes],
        error: Optional[str] = None,
    ):
        self.node = node
        self._pipeline = serialized_pipeline
        self._result = result
        self.error = error

    @property
    def pipeline(self) -> Pipeline:
        import cloudpickle

        return cloudpickle.loads(self._pipeline)  # type: ignore

    @property
    def result(
        self,
    ) -> Optional[Tuple[Result[PipelineResult, PipelineResult], LogType]]:
        import cloudpickle

        return cloudpickle.loads(self._result) if self._result else None

    def __str__(self) -> str:
        return f"DeploymentExecutionResult(node={self.node}, result={self.result}, error={self.error})"

    def __repr__(self) -> str:
        return self.__str__()

    def __json__(self) -> DeploymentExecutionResultRepresentation:
        return {
            "node": self.node.__json__(),
            "pipeline": base64.b64encode(self._pipeline).decode("utf-8"),
            "result": base64.b64encode(self._result).decode("utf-8")
            if self._result
            else None,
            "error": self.error,
        }

    @classmethod
    def from_json(
        cls, data: DeploymentExecutionResultRepresentation
    ) -> DeploymentExecutionResult:
        return cls(
            Node.from_json(data["node"]),
            base64.b64decode(data["pipeline"]),
            base64.b64decode(data["result"]) if data["result"] else None,
            data["error"],
        )


@dataclass(frozen=True)
class ExperimentExecutionInformation:
    status: ExperimentStatus
    experiment: Optional[Experiment]
    execution_result: Union[None, Exception, List[DeploymentExecutionResult]]

    def __json__(self) -> ExperimentExecutionInformationRepresentation:
        execution_result: Union[
            None, str, List[DeploymentExecutionResultRepresentation]
        ] = None
        if isinstance(self.execution_result, list):
            execution_result = [x.__json__() for x in self.execution_result]
        elif isinstance(self.execution_result, Exception):
            execution_result = str(self.execution_result.__reduce__())
        return {
            "status": self.status.__json__(),
            "experiment": self.experiment.__json__() if self.experiment else None,
            "execution_result": execution_result,
        }

    @classmethod
    def from_json(
        cls, data: ExperimentExecutionInformationRepresentation
    ) -> ExperimentExecutionInformation:
        status = ExperimentStatus.from_json(data["status"])
        experiment = (
            Experiment.from_json(data["experiment"]) if data["experiment"] else None
        )
        execution_result_data = data["execution_result"]
        execution_result: Union[None, Exception, List[DeploymentExecutionResult]] = None
        if execution_result_data:
            if isinstance(execution_result_data, list):
                execution_result = [
                    DeploymentExecutionResult.from_json(x)
                    for x in execution_result_data
                ]
            else:
                execution_result = Exception(execution_result_data)
        return cls(status, experiment, execution_result)
