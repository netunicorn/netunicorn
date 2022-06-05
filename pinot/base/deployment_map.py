from __future__ import annotations

import copy
from enum import Enum
from typing import Iterator, List
from dataclasses import dataclass

from returns.result import Result

from pinot.base import Pipeline
from pinot.base.minions import Minion
from pinot.base.pipeline import PipelineResult


class DeploymentStatus(Enum):
    UNKNOWN = 0
    STARTING = 1
    RUNNING = 2
    FINISHED = 3


@dataclass
class Deployment:
    minion: Minion
    pipeline: Pipeline


class DeploymentMap:
    def __init__(self, keep_alive_timeout_minutes: int = 10):
        """
        :param keep_alive_timeout_minutes: how long to wait for a minion
         after deployer showed that it's unresponsive to recover
        """
        self.deployment_map: List[Deployment] = []
        self.keep_alive_timeout_minutes = keep_alive_timeout_minutes

    def append(self, minion: Minion, pipeline: Pipeline) -> DeploymentMap:
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

    def __add__(self, other) -> DeploymentMap:
        new_map = copy.deepcopy(self)
        new_map.deployment_map.extend(other.deployment_map.deployment_map)
        return new_map


@dataclass
class DeploymentExecutionResult:
    minion: Minion
    pipeline: Pipeline
    result: Result[PipelineResult, PipelineResult]
