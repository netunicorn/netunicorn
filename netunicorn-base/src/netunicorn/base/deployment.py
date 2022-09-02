from __future__ import annotations

from typing import Optional
from cloudpickle import dumps

from .minions import Minion
from .pipeline import Pipeline
from .task import TaskDispatcher
from .utils import SerializedPipelineType


class Deployment:
    def __init__(self, minion: Minion, pipeline: Pipeline):
        self.minion = minion
        self.prepared = False
        self.executor_id = "Unknown"
        self.error: Optional[Exception] = None
        self.pipeline: SerializedPipelineType = b''
        self.environment_definition = pipeline.environment_definition

        for element in pipeline.tasks:
            element = [x.dispatch(minion) if isinstance(x, TaskDispatcher) else x for x in element]
            for x in element:
                self.environment_definition.commands.extend(x.requirements)

        self.pipeline = dumps(pipeline)

    def __str__(self):
        return f"Deployment: Minion={self.minion.name}, executor_id={self.executor_id}, prepared={self.prepared}"

    def __repr__(self):
        return self.__str__()
