from __future__ import annotations

import copy
from enum import Enum
from typing import Iterator, List, Optional
from dataclasses import dataclass

from returns.result import Result

from unicorn.base import Pipeline, Task
from unicorn.base.minions import Minion
from unicorn.base.pipeline import PipelineResult
from unicorn.base.task import TaskDispatcher


class ExperimentStatus(Enum):
    UNKNOWN = 0
    PREPARING = 1
    READY = 2
    RUNNING = 3
    FINISHED = 4


class Deployment:
    def __init__(self, minion: Minion, pipeline: Pipeline):
        self.minion = minion
        self.prepared = False
        self.executor_id = "Unknown"
        self.error: Optional[Exception] = None
        self.pipeline: List[List[Task]] = []
        self.environment_definition = pipeline.environment_definition

        for element in pipeline.tasks:
            element = [x.dispatch(minion) if isinstance(x, TaskDispatcher) else x for x in element]
            for x in element:
                self.environment_definition.commands.extend(x.requirements)
            self.pipeline.append(element)


class Experiment:
    def __init__(self, keep_alive_timeout_minutes: int = 10):
        """
        :param keep_alive_timeout_minutes: how long to wait for a minion
         after deployer showed that it's unresponsive to recover
        """
        self.deployment_map: List[Deployment] = []
        self.keep_alive_timeout_minutes = keep_alive_timeout_minutes

    def append(self, minion: Minion, pipeline: Pipeline) -> Experiment:
        self.deployment_map.append(Deployment(minion, pipeline))
        return self

    def __getitem__(self, item) -> Deployment:
        return self.deployment_map[item]

    def __iter__(self) -> Iterator[Deployment]:
        return iter(self.deployment_map)

    def __len__(self) -> int:
        return len(self.deployment_map)

    def __str__(self) -> str:
        return str(self.deployment_map)

    def __repr__(self) -> str:
        return str(self)

    def __add__(self, other) -> Experiment:
        new_map = copy.deepcopy(self)
        new_map.deployment_map.extend(other.deployment_map.deployment_map)
        return new_map


@dataclass
class ExperimentExecutionResult:
    minion: Minion
    pipeline: Pipeline
    result: Result[PipelineResult, PipelineResult]
