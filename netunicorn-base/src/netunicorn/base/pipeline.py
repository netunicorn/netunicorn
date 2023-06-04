"""
Abstrcations for Pipeline representation.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Collection, List, Optional, Set, Union
from warnings import warn

from .environment_definitions import DockerImage, EnvironmentDefinition
from .task import TaskElement

PipelineElement = Union[TaskElement, Collection[TaskElement]]


class Pipeline:
    """
    Pipeline is a class that takes a tuple of Tasks and executes them in order.
    Each element in the tuple should be either a Task or a tuple of Tasks.
    Pipeline will execute elements in order and return the combined result of all tasks.
    If element is a tuple of tasks, these tasks would be executed in parallel.

    | The result of pipeline execution would be one of the following:
    | - Success: if all tasks succeed, then Success is returned
    | - Failure: if any task fails, then Failure is returned

    | Returning object will always contain a Result object for each task executed.
    | If early_stopping is set to True, then any task after first failed wouldn't be executed.

    :param tasks: tasks (ordered by stages) to be executed
    :param early_stopping: whether to stop executing tasks after first failure
    :param report_results: whether executor should connect core services to report pipeline results in the end
    :param environment_definition: environment definition for the pipeline
    """

    def __init__(
        self,
        tasks: Collection[PipelineElement] = (),
        early_stopping: bool = True,
        report_results: bool = True,
        environment_definition: Optional[EnvironmentDefinition] = None,
    ):
        self.name: str = str(uuid.uuid4())
        """
        Pipeline name.
        """

        self.task_names: Set[str] = set()
        """
        Task names in the pipeline, used for dictionary of results.
        """

        self.early_stopping: bool = early_stopping
        """
        Whether to stop executing tasks after first failure.
        """

        self.tasks: List[List[TaskElement]] = []
        """
        Tasks stages to be executed.
        """

        self.report_results: bool = report_results
        """
        Whether executor should connect core services to report pipeline results in the end.
        """

        self.environment_definition: EnvironmentDefinition = (
            environment_definition or DockerImage()
        )
        """
        Environment definition for the pipeline.
        """

        for element in tasks:
            self.then(element)

    @staticmethod
    def __element_to_stage(element: PipelineElement) -> List[TaskElement]:
        if not isinstance(element, Collection):
            element = [element]
        if not isinstance(element, list):
            element = list(element)
        return element

    def __check_tasks_names(self, stage: List[TaskElement]) -> None:
        for task in stage:
            if task.name in self.task_names:
                warn(
                    f"Task with name {task.name} already exists in the current pipeline {self.__str__()}. "
                    "Please, note that execution results of these tasks could be mixed or overwritten."
                )
            self.task_names.add(task.name)

    def then(self, element: PipelineElement) -> Pipeline:
        """
        Add a task or list of tasks as a separate stage to the end of the pipeline.

        :param element: a task or tuple of tasks to be added
        :return: self
        """
        element = self.__element_to_stage(element)
        self.__check_tasks_names(element)
        self.tasks.append(element)
        return self

    def copy(self) -> Pipeline:
        """
        Return a copy of the pipeline.

        :return: a copy of the pipeline
        """
        return Pipeline(deepcopy(self.tasks), self.early_stopping)

    def __str__(self) -> str:
        return f"Pipeline({self.name}): {self.tasks}"

    def __repr__(self) -> str:
        return str(self)
