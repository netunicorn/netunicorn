from __future__ import annotations

import copy
from enum import Enum
from typing import Iterator, List, Tuple
from dataclasses import dataclass

from returns.result import Result

from .minions import Minion, MinionPool
from .deployment import Deployment
from .pipeline import Pipeline, PipelineResult
from .utils import LogType


class ExperimentStatus(Enum):
    UNKNOWN = 0
    PREPARING = 1
    READY = 2
    RUNNING = 3
    FINISHED = 4


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

    def map(self, minions: MinionPool, pipeline: Pipeline) -> Experiment:
        for minion in minions:
            self.append(minion, pipeline)
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

    def __add__(self, other: Experiment) -> Experiment:
        new_map = copy.deepcopy(self)
        new_map.deployment_map.extend(other.deployment_map)
        return new_map


@dataclass
class ExperimentExecutionResult:
    minion: Minion
    pipeline: SerializedExperimentExecutionResult
    result: Tuple[Result[PipelineResult, PipelineResult], LogType]

    def __str__(self) -> str:
        return f"ExperimentExecutionResult(minion={self.minion}, result={self.result})"

    def __repr__(self):
        return self.__str__()


SerializedExperimentExecutionResult = bytes
