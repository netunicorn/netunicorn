import sys
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from netunicorn.base.experiment import Experiment

if sys.version_info >= (3, 9):
    from typing import TypeAlias

    from typing_extensions import TypedDict
else:
    from typing_extensions import TypeAlias, TypedDict

ConnectorContext: TypeAlias = Optional[Dict[str, Dict[str, str]]]


class ExecutorsCancellationRequest(TypedDict):
    executors: List[str]
    cancellation_context: ConnectorContext


class BasePreprocessor(ABC):
    @abstractmethod
    def __call__(self, experiment_id: str, experiment: Experiment) -> Experiment:
        return experiment


class BasePostprocessor(ABC):
    @abstractmethod
    def __call__(self, experiment_id: str, experiment: Experiment) -> Experiment:
        return experiment
