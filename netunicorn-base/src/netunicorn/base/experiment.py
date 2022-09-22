from __future__ import annotations

import base64
import copy
from enum import Enum
from typing import Iterator, List, Tuple, Optional
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

    def __json__(self):
        return self.value

    @classmethod
    def from_json(cls, value: str) -> ExperimentStatus:
        return cls(value)


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

    def __json__(self) -> dict:
        return {
            "deployment_map": [x.__json__() for x in self.deployment_map],
            "keep_alive_timeout_minutes": self.keep_alive_timeout_minutes,
        }

    @classmethod
    def from_json(cls, data: dict):
        instance = cls.__new__(cls)
        instance.deployment_map = [Deployment.from_json(x) for x in data["deployment_map"]]
        instance.keep_alive_timeout_minutes = data["keep_alive_timeout_minutes"]
        return instance

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


class ExperimentExecutionResult:
    def __init__(self, minion: Minion, serialized_pipeline: bytes, result: Optional[bytes], error: Optional[str] = None):
        self.minion = minion
        self._pipeline = serialized_pipeline
        self._result = result
        self.error = error

    @property
    def pipeline(self) -> Pipeline:
        import cloudpickle
        return cloudpickle.loads(self._pipeline)

    @property
    def result(self) -> Optional[Tuple[Result[PipelineResult, PipelineResult], LogType]]:
        import cloudpickle
        return cloudpickle.loads(self._result) if self._result else None

    def __str__(self) -> str:
        return f"ExperimentExecutionResult(minion={self.minion}, result={self.result}, error={self.error})"

    def __repr__(self):
        return self.__str__()

    def __json__(self) -> dict:
        return {
            "minion": self.minion.__json__(),
            "pipeline": base64.b64encode(self._pipeline).decode("utf-8"),
            "result": base64.b64encode(self._result).decode("utf-8") if self._result else None,
            "error": self.error,
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            Minion.from_json(data["minion"]),
            base64.b64decode(data["pipeline"]),
            base64.b64decode(data["result"]) if data["result"] else None,
            data["error"],
        )


SerializedExperimentExecutionResult = bytes
