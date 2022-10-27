from __future__ import annotations

from base64 import b64decode
from typing import Optional

import netunicorn.base.environment_definitions

from .minions import Minion
from .pipeline import Pipeline
from .task import TaskDispatcher
from .utils import SerializedPipelineType

try:
    import cloudpickle  # it's needed only on client side, but this module is also imported on engine side
    import netunicorn.library

    cloudpickle.register_pickle_by_value(netunicorn.library)
except ImportError:
    pass


class Deployment:
    def __init__(self, minion: Minion, pipeline: Pipeline):
        self.minion = minion
        self.prepared = False
        self.executor_id = ""
        self.error: Optional[Exception] = None
        self.pipeline: SerializedPipelineType = b""
        self.environment_definition = pipeline.environment_definition

        for i, element in enumerate(pipeline.tasks):
            pipeline.tasks[i] = [
                x.dispatch(minion) if isinstance(x, TaskDispatcher) else x
                for x in element
            ]
            for x in pipeline.tasks[i]:
                self.environment_definition.commands.extend(x.requirements)

        self.pipeline = cloudpickle.dumps(pipeline)

    def __str__(self):
        return f"Deployment: Minion={self.minion.name}, executor_id={self.executor_id}, prepared={self.prepared}"

    def __repr__(self):
        return self.__str__()

    def __json__(self):
        return {
            "minion": self.minion.__json__(),
            "prepared": self.prepared,
            "executor_id": self.executor_id,
            "error": str(self.error) if self.error else None,
            "pipeline": self.pipeline,
            "environment_definition": self.environment_definition.__json__(),
            "environment_definition_type": self.environment_definition.__class__.__name__,
        }

    @classmethod
    def from_json(cls, data: dict):
        instance = cls.__new__(cls)

        instance.minion = Minion.from_json(data["minion"])
        instance.prepared = data["prepared"]
        instance.executor_id = data["executor_id"]
        instance.error = Exception(data["error"]) if data["error"] else None
        instance.pipeline = b64decode(data["pipeline"])
        instance.environment_definition = getattr(
            netunicorn.base.environment_definitions, data["environment_definition_type"]
        ).from_json(data["environment_definition"])
        return instance
