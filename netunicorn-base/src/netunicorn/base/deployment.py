"""
Single deployment of pipeline on node.
"""
from __future__ import annotations

from base64 import b64decode
from copy import deepcopy
from typing import List, Optional, cast

import netunicorn.base.environment_definitions

from .nodes import Node
from .pipeline import Pipeline
from .task import Task, TaskDispatcher
from .types import DeploymentRepresentation
from .utils import SerializedPipelineType

try:
    import cloudpickle  # it's needed only on client side, but this module is also imported on engine side
    import netunicorn.library

    cloudpickle.register_pickle_by_value(netunicorn.library)
except ImportError:
    pass


class Deployment:
    """
    Single deployment of pipeline on node.

    :param node: Node to deploy pipeline on
    :param pipeline: Pipeline to deploy
    :param keep_alive_timeout_minutes: time to wait for executor update before timeout
    :param cleanup: whether to remove artifacts (e.g., Docker image and containers) after execution
    """

    def __init__(
        self,
        node: Node,
        pipeline: Pipeline,
        keep_alive_timeout_minutes: int = 10,
        cleanup: bool = True,
    ):
        self.node: Node = node
        """
        Node to deploy pipeline on
        """

        self.prepared: bool = False
        """
        if False, deployment is not prepared yet or failed during preparation
        """

        self.executor_id: str = ""
        """
        ID of executor on node
        """

        self.error: Optional[Exception] = None
        """
        if deployment failed, this field contains error
        """

        self.pipeline: SerializedPipelineType = b""
        """
        Serialized Pipeline to be deployed
        """

        self.environment_definition: netunicorn.base.environment_definitions.EnvironmentDefinition = deepcopy(
            pipeline.environment_definition
        )
        """
        Environment definition to use for deployment
        """

        self.keep_alive_timeout_minutes: int = keep_alive_timeout_minutes
        """
        time to wait for executor update before timeout
        """

        self.cleanup: bool = cleanup
        """
        if True, corresponding artifacts (Docker image and containers) will be removed after execution
        """

        self._validate_deployment(node, pipeline)

        pipeline = deepcopy(pipeline)

        for i, element in enumerate(pipeline.tasks):
            pipeline.tasks[i] = [
                x.dispatch(node) if isinstance(x, TaskDispatcher) else x
                for x in element
            ]
            tasks_list: List[Task] = cast(List[Task], pipeline.tasks[i])
            for x in tasks_list:
                self.environment_definition.commands.extend(x.requirements)

        self.pipeline = cloudpickle.dumps(pipeline)

    @staticmethod
    def _validate_deployment(node: Node, pipeline: Pipeline) -> None:
        if type(pipeline.environment_definition) not in node.available_environments:
            raise ValueError(
                f"Node {node.name} does not support environment {type(pipeline.environment_definition).__name__}"
            )

    def __str__(self) -> str:
        return f"Deployment: Node={self.node.name}, executor_id={self.executor_id}, prepared={self.prepared}, error={self.error}"

    def __repr__(self) -> str:
        return self.__str__()

    def __json__(self) -> DeploymentRepresentation:
        return {
            "node": self.node.__json__(),
            "prepared": self.prepared,
            "executor_id": self.executor_id,
            "error": str(self.error) if self.error else None,
            "pipeline": self.pipeline,
            "keep_alive_timeout_minutes": self.keep_alive_timeout_minutes,
            "cleanup": self.cleanup,
            "environment_definition": self.environment_definition.__json__(),
            "environment_definition_type": self.environment_definition.__class__.__name__,
        }

    @classmethod
    def from_json(cls, data: DeploymentRepresentation) -> Deployment:
        """
        Create Deployment from JSON representation

        :param data: JSON representation of Deployment
        :return: Deserialized Deployment
        """
        instance = cls.__new__(cls)

        instance.node = Node.from_json(data["node"])
        instance.prepared = data["prepared"]
        instance.executor_id = data["executor_id"]
        instance.error = Exception(data["error"]) if data["error"] else None
        instance.pipeline = b64decode(data["pipeline"])
        instance.keep_alive_timeout_minutes = data["keep_alive_timeout_minutes"]
        instance.cleanup = data.get("cleanup", True)
        instance.environment_definition = getattr(
            netunicorn.base.environment_definitions, data["environment_definition_type"]
        ).from_json(data["environment_definition"])
        return instance
