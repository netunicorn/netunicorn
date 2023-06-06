"""
Experiment-related entities and classes.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, List, Optional, Sequence, Tuple, Union, cast

from returns.pipeline import is_successful
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
    """
    Represents a status of an experiment.
    """

    UNKNOWN = 0
    """
    Unknown status.
    """

    PREPARING = 1
    """
    Experiment is under preparation.
    """

    READY = 2
    """
    Experiment is prepared and ready to be started.
    """

    RUNNING = 3
    """
    Experiment is running.
    """

    FINISHED = 4
    """
    Experiment is finished.
    """

    def __json__(self) -> int:
        return self.value

    @classmethod
    def from_json(cls, value: int) -> ExperimentStatus:
        """
        Converts a JSON representation of an experiment status to an instance of ExperimentStatus.

        :param value: experiment status value.
        :return: an instance of ExperimentStatus.
        """
        return cls(value)


class Experiment:
    """
    Represents an experiment that contains a mapping of pipelines to nodes.

    :param deployment_context: deployment context to be used by connectors.
    """

    def __init__(
        self, deployment_context: Optional[Dict[str, Dict[str, str]]] = None
    ) -> None:
        self.deployment_map: List[Deployment] = []
        """
        a list of deployments
        """

        self.deployment_context: Optional[
            Dict[str, Dict[str, str]]
        ] = deployment_context
        """
        A dictionary that contains a context for deployments.
            Context is to be provided by connectors. 
            Format: {connector_name: {key: value}}
        """

    def append(self, node: Node, pipeline: Pipeline) -> Experiment:
        """
        Append a new deployment (mapping of pipeline to a node) to the experiment.

        :param node: a node to deploy the pipeline to.
        :param pipeline: a pipeline to deploy.
        :return: self.
        """

        self.deployment_map.append(Deployment(node, pipeline))
        return self

    def map(self, pipeline: Pipeline, nodes: Sequence[Node]) -> Experiment:
        """
        Map a pipeline to a sequence of nodes.

        :param pipeline: a pipeline to deploy.
        :param nodes: a sequence of nodes to deploy the pipeline to.
        :return: self.
        """

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
        """
        Creates an instance of Experiment from a JSON representation.

        :param data: a JSON representation of an experiment.
        :return: an instance of Experiment.
        """
        instance = cls.__new__(cls)
        instance.deployment_map = [
            Deployment.from_json(x) for x in data["deployment_map"]
        ]
        instance.deployment_context = data.get("deployment_context")
        return instance

    def __getitem__(self, item: int) -> Deployment:
        """
        Returns a deployment by index.

        :param item: an index of a deployment.
        :return: a deployment.
        """
        return self.deployment_map[item]

    def __iter__(self) -> Iterator[Deployment]:
        """
        Returns an iterator over deployments.

        :return: an iterator over deployments.
        """
        return iter(self.deployment_map)

    def __len__(self) -> int:
        """
        Returns a number of deployments in the experiment.

        :return: a number of deployments in the experiment.
        :meta public:
        """
        return len(self.deployment_map)

    def __str__(self) -> str:
        return "\n".join([f" - {x}" for x in self.deployment_map])

    def __repr__(self) -> str:
        return self.__str__()

    def __add__(self, other: Experiment) -> Experiment:
        """
        Concatenates two experiments resulting in a union of deployments.

        :param other: an experiment to concatenate with.
        :return: a new experiment.
        """

        new_map = copy.deepcopy(self)
        new_map.deployment_map.extend(other.deployment_map)
        if other.deployment_context:
            if new_map.deployment_context is None:
                new_map.deployment_context = {}
            new_map.deployment_context.update(other.deployment_context)
        return new_map


class DeploymentExecutionResult:
    """
    Stores a result (or ongoing information) of a deployment execution.

    :param node: a node that was used for deployment.
    :param serialized_pipeline: a serialized pipeline.
    :param result: a result of a deployment execution.
    :param error: an error message if deployment failed.
    """

    def __init__(
        self,
        node: Node,
        serialized_pipeline: bytes,
        result: Optional[bytes],
        error: Optional[str] = None,
    ):
        self.node: Node = node
        """
        a node that was used for deployment
        """

        self._pipeline: bytes = serialized_pipeline
        """
        a serialized pipeline
        """

        self._result: Optional[bytes] = result
        """
        Deployment execution result
        """

        self.error: Optional[str] = error
        """
        An error message if deployment failed.
        """

    @property
    def pipeline(self) -> Pipeline:
        """
        Returns a pipeline that was used for deployment.

        :return: a pipeline that was used for deployment.
        """
        import cloudpickle

        return cast(Pipeline, cloudpickle.loads(self._pipeline))

    @property
    def result(
        self,
    ) -> Optional[Tuple[Result[PipelineResult, PipelineResult], LogType]]:
        """
        Returns a result of a deployment execution and logs.

        :return: a tuple of (execution result, logs).
        """
        import cloudpickle

        return cloudpickle.loads(self._result) if self._result else None

    def __str__(self) -> str:
        text = "DeploymentExecutionResult:\n  Node: {self.node}\n"
        result = self.result
        if result:
            text += f"  Result: {type(result[0])}\n"
            if not is_successful(result[0]):
                text += f"   {result[0]}\n"
            else:
                for task_id, task_result in result[0].unwrap().items():
                    text += f"    {task_id}: {task_result}\n"
            text += f"  Logs:\n"
            for line in result[1]:
                text += f"    {line}"
        if self.error:
            text += f"  Error: {self.error}\n"
        text += "\n"
        return text

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
        """
        Returns an instance of DeploymentExecutionResult from a JSON representation.

        :param data: a JSON representation of a deployment execution result.
        :return: an instance of DeploymentExecutionResult.
        """
        return cls(
            Node.from_json(data["node"]),
            base64.b64decode(data["pipeline"]),
            base64.b64decode(data["result"]) if data["result"] else None,
            data["error"],
        )


@dataclass(frozen=True)
class ExperimentExecutionInformation:
    """
    Stores information about an experiment execution.

    :param status: a status of an experiment execution.
    :param experiment: a definition of an experiment.
    :param execution_result: a result of an experiment execution.
    """

    status: ExperimentStatus
    """
    Describes the status of an experiment execution.
    """

    experiment: Optional[Experiment]
    """
    Stores the definition of the experiment.
    """

    execution_result: Union[None, Exception, List[DeploymentExecutionResult]]
    """
    Stores either an Exception if experiment execution failed or a list of deployment execution results.
    """

    def __str__(self) -> str:
        text = (
            f"ExperimentExecutionInformation:\n"
            f"status: {self.status}\n"
            f"experiment: \n"
            f"{self.experiment}\n"
            f"execution_result:\n"
            f"{self.execution_result}\n"
        )
        return text

    def __repr__(self) -> str:
        return self.__str__()

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
        """
        Returns an instance of ExperimentExecutionInformation from a JSON representation.

        :param data: a JSON representation of an experiment execution information.
        :return: an instance of ExperimentExecutionInformation.
        """

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
