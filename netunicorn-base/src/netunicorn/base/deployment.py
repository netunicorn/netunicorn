from __future__ import annotations

from typing import Optional

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
        self.executor_id = "Unknown"
        self.error: Optional[Exception] = None
        self.pipeline: SerializedPipelineType = b''
        self.environment_definition = pipeline.environment_definition

        for i, element in enumerate(pipeline.tasks):
            pipeline.tasks[i] = [x.dispatch(minion) if isinstance(x, TaskDispatcher) else x for x in element]
            for x in pipeline.tasks[i]:
                self.environment_definition.commands.extend(x.requirements)

        self.pipeline = cloudpickle.dumps(pipeline)

    def __str__(self):
        return f"Deployment: Minion={self.minion.name}, executor_id={self.executor_id}, prepared={self.prepared}"

    def __repr__(self):
        return self.__str__()
