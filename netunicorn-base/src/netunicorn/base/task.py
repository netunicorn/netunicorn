from __future__ import annotations

import uuid
from typing import Any, Collection, List, Union

from returns.result import Failure, Result, Success

from .minions import Minion
from .utils import safe

# Keep classes for export
Success = Success
Failure = Failure


class Task:
    """
    This is a base class for all tasks. All new task classes should inherit from this class.
    The task instance should encapsulate all the logic and data needed to execute the task.
    Task entrypoint is the run() method.
    Task class can have requirements - commands to be executed to change environment to support this task.
    These requirements would be executed with OS shell during environment setup.
    Each task is to be implemented for a specific architecture, platform, or combination (like Linux + arm64).
    TaskDispatcher can be used for selecting a specific task for the given architecture, platform, or combination.

    Task always returns a Result object.
    - If the task's `run` method returns Result object by itself, you'll receive this Result object
    - If the task's `run` method returns any other object, you'll receive a Success with returned_value encapsulated
    - If the task's `run` method fires an exception, you'll receive a Failure with the exception encapsulated
    """

    # Task installation requirements
    requirements: List[str] = []

    # this variable would be overwritten before task start with results of previous tasks
    previous_steps: List[Union[Result, Collection[Result]]] = []

    def __call__(self):
        return self.run()

    def __str__(self):
        return self.name

    def add_requirement(self, command: str) -> Task:
        """
        This method adds a requirement to the task.
        :param command:
        :return:
        """
        self.requirements.append(command)
        return self

    def __init__(self):
        """
        ## This method is to be overridden by your implementation. ##
        This is a constructor for the task. Any variables (state) that `run` method should use should be provided here.
        """
        self.name = str(uuid.uuid4())  # Each task should have a name
        self.run = safe(
            self.run
        )  # Each task should have its `run` method protected by `safe` decorator

    def run(self) -> Any:
        """
        ## This method is to be overridden by your implementation. ##
        This is the entrypoint for the task.
        This method should never have any arguments except `self`. Any arguments that task would use for execution
        should be provided to the constructor and used later by this method.
        This method will always return a Result object. If this method doesn't return a Result object,
        it will be encapsulated into a Result object.
        :return: Result of the execution
        """
        raise NotImplementedError


class TaskDispatcher:
    """
    This class is a wrapper for several tasks that are designed to implement the same functionality for different
    architectures, platforms, etc. It is designed to be used as a base class for your task dispatcher.

    Dispatching is done by calling the dispatch method. This method should return the proper task for the minion
    given minion information (such as architecture, platform, etc).
    """

    def dispatch(self, minion: Minion) -> Task:
        raise NotImplementedError
