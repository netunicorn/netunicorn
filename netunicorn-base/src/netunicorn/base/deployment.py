from __future__ import annotations

from base64 import b64decode
from copy import deepcopy
from typing import Optional

import netunicorn.base.environment_definitions

from .nodes import Node
from .pipeline import Pipeline
from .task import TaskDispatcher
from .types import DeploymentRepresentation
from .utils import SerializedPipelineType

try:
    import cloudpickle  # it's needed only on client side, but this module is also imported on engine side
    import netunicorn.library

    cloudpickle.register_pickle_by_value(netunicorn.library)
except ImportError:
    pass


class Deployment:
    def __init__(
        self,
        node: Node,
        pipeline: Pipeline,
        keep_alive_timeout_minutes: int = 10,
        cleanup: bool = True,
    ):
        self.node = node
        self.prepared = False
        self.executor_id = ""
        self.error: Optional[Exception] = None
        self.pipeline: SerializedPipelineType = b""
        self.environment_definition = deepcopy(pipeline.environment_definition)
        self.keep_alive_timeout_minutes = keep_alive_timeout_minutes
        self.cleanup = cleanup

        pipeline = deepcopy(pipeline)

        for i, element in enumerate(pipeline.tasks):
            pipeline.tasks[i] = [
                x.dispatch(node) if isinstance(x, TaskDispatcher) else x
                for x in element
            ]
            for x in pipeline.tasks[i]:
                # now it's only Tasks
                self.environment_definition.commands.extend(x.requirements)  # type: ignore

        self.pipeline = cloudpickle.dumps(pipeline)

    def __str__(self) -> str:
        return f"Deployment: Node={self.node.name}, executor_id={self.executor_id}, prepared={self.prepared}"

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
