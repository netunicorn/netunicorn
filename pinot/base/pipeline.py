from __future__ import annotations

from copy import deepcopy

import uuid

from returns.result import Result
from typing import Union, Collection
from .task import Task
from .environment_definitions import EnvironmentDefinition, ShellExecution

PipelineElement = Union[Task, Collection[Task]]
PipelineElementResult = Union[Result, Collection[Result]]
PipelineResult = Collection[PipelineElementResult]


class Pipeline:
    """
    Pipeline is a class that takes a tuple of Tasks and executes them in order.
    Each element in the tuple should be either a Task or a tuple of Tasks.
    Pipeline will execute elements in order and return the combined result of all tasks.
    If element is a tuple of tasks, these tasks would be executed in parallel.

    The result of pipeline execution would be one of the following:
    - Success: if all tasks succeed, then Success is returned
    - Failure: if any task fails, then Failure is returned

    Returning object will always contain a Result object for each task executed.
    If early_stopping is set to True, then any task after first failed wouldn't be executed.
    """

    def __init__(
            self,
            tasks: Collection[PipelineElement] = (),
            early_stopping: bool = True,
            report_results: bool = True
    ):
        """
        Initialize Pipeline with a tuple of Tasks and early_stopping flag.
        :param tasks: a tuple of tasks to be executed
        :param early_stopping: whether to stop executing tasks after first failure
        :param report_results: whether executor should connect director services to report pipeline results after exec
        """
        self.name = str(uuid.uuid4())
        self.early_stopping = early_stopping
        self.tasks = tuple(tasks)
        self.report_results = report_results

        self.environment_definition: EnvironmentDefinition = ShellExecution()
        for element in self.tasks:
            self.add_requirements(element)

    def then(self, element: PipelineElement) -> Pipeline:
        """
        Add a task or tuple of tasks to the end of the pipeline.
        :param element: a task or tuple of tasks to be added
        :return: self
        """
        self.add_requirements(element)
        self.tasks = self.tasks + (element,)
        return self

    def add_requirements(self, element: PipelineElement) -> None:
        if not isinstance(element, Collection):
            element = (element,)

        for task in element:
            self.environment_definition.add_requirements(task)

    def copy(self) -> Pipeline:
        """
        Return a copy of the pipeline.
        :return: a copy of the pipeline
        """
        return Pipeline(deepcopy(self.tasks), self.early_stopping)

    def __str__(self):
        return f"Pipeline({self.name}): {self.tasks}"

    def __repr__(self):
        return str(self)
