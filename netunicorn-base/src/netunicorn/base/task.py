from __future__ import annotations

import copy
import uuid
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Union

from returns.result import Failure, Success

from .nodes import Node
from .types import PipelineResult

# Keep classes for export
Success = Success
Failure = Failure


class Task(ABC):
    """
    | This is a base class for all tasks. All new task classes should inherit from this class.
    | The task instance should encapsulate all the logic and data needed to execute the task.
    | Task entrypoint is the run() method.
    | Task class can have requirements - commands to be executed to change environment to support this task.
    | These requirements would be executed with OS shell during environment setup.
    | Each task is to be implemented for a specific architecture, platform, or combination (like Linux + arm64).
    | TaskDispatcher can be used for selecting a specific task for the given architecture, platform, or combination.

    | Task always returns a Result object.
    | - If the task's `run` method returns Result object by itself, you'll receive this Result object
    | - If the task's `run` method returns any other object, you'll receive a Success with returned_value encapsulated
    | - If the task's `run` method fires an exception, you'll receive a Failure with the exception encapsulated

    | When creating your own tasks, please, do not forget to call `super().__init__(*args, **kwargs)` in your implementation
        to properly initialize the base class.

    :param name: Name of the task. If not provided, a random UUID will be used.
    """

    requirements: List[str] = []
    """
    A list of commands to be executed to change environment to support this task.
    """

    previous_steps: PipelineResult = {}
    r"""
    Stores results of previous steps with task name as a key and list of results as a value.
        Several results could be stored for each task if it was executed several times.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name or str(uuid.uuid4())
        self.requirements = copy.deepcopy(self.requirements)

    def __call__(self) -> Any:
        """
        This method is called when you call the task instance as a function. It's a shortcut for `run` method.

        :return: Result of the execution
        """
        return self.run()

    def __repr__(self) -> str:
        type_ = type(self)
        module = type_.__module__
        qualname = type_.__qualname__
        return f"<{module}.{qualname} with name {self.name}>"

    def __str__(self) -> str:
        return self.__repr__()

    def add_requirement(self, command: str) -> Task:
        """
        | This method adds a requirement to the requirements of the instance of the task.
        | Please, note that the requirement would be added to the instance, not to all instances of the class.
        | Use it to provide additional requirements that should be executed only once despite the number of instances.

        :param command: Command to be executed to change environment to support this task.
        :return: self
        """
        self.requirements = copy.deepcopy(self.requirements)
        self.requirements.append(command)
        return self

    @abstractmethod
    def run(self) -> Any:
        """
        | ## This method is to be overridden by your implementation. ##
        | This is the entrypoint for the task.
        | This method should never have any arguments except `self`. Any arguments that task would use for execution
            should be provided to the constructor and used later by this method.
        | This method will always return a Result object. If this method doesn't return a Result object,
            it will be encapsulated into a Result object.

        :return: Result of the execution
        """
        raise NotImplementedError


class TaskDispatcher(ABC):
    """
    | This class is a wrapper for several tasks that are designed to implement the same functionality
        but depend on node attributes. Most often you either want to use a specific
        implementation for a specific architecture (e.g., different Tasks for Windows and Linux),
        or instantiate a task with some specific parameters for a specific node (e.g., node-specific IP address).
    | You should implement your own TaskDispatcher class and override the dispatch method.
    |
    | You also should provide and use any variables (state) that `run` method would use in the constructor of this class
        and pass them to the constructor of the task implementation.
    |
    | Dispatching is done by calling the dispatch method that you should implement.

    :param name: Name of the task. If not provided, a random UUID will be used.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        self.name = name or str(uuid.uuid4())
        """
        Name of the task.
        """

    @abstractmethod
    def dispatch(self, node: Node) -> Task:
        """
        | This method takes a node and should return and instance of the task that is designed to be executed on this node.
        | The instance could depend on the node information (such as architecture, platform, properties, etc).
        |
        | Do not forget to pass all arguments and variables to the constructor of the task implementation.

        :param node: Node instance
        :return: Task instance selected based on the node information
        """
        raise NotImplementedError


TaskElement = Union[Task, TaskDispatcher]
