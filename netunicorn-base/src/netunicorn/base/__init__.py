"""
A base module with all the core classes and functions.
"""

from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from .architecture import Architecture
from .environment_definitions import DockerImage, ShellExecution
from .execution_graph import ExecutionGraph
from .experiment import Experiment, ExperimentExecutionInformation, ExperimentStatus
from .nodes import Node
from .pipeline import CyclePipeline, Pipeline
from .task import Task, TaskDispatcher
from .types import FlagValues

__all__ = [
    "Experiment",
    "ExperimentStatus",
    "ExperimentExecutionInformation",
    "Pipeline",
    "CyclePipeline",
    "ExecutionGraph",
    "Task",
    "TaskDispatcher",
    "Result",
    "Success",
    "Failure",
    "is_successful",
    "FlagValues",
    "ShellExecution",
    "DockerImage",
    "Node",
    "Architecture",
]
