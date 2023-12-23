"""
Abstrcations for Pipeline representation.
"""

from __future__ import annotations

from typing import Any, Collection, Dict, List, Optional, Union

import networkx as nx

from .environment_definitions import EnvironmentDefinition
from .execution_graph import ExecutionGraph
from .task import TaskElement

PipelineElement = Union[TaskElement, Collection[TaskElement]]


class Pipeline(ExecutionGraph):
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
        super().__init__(
            early_stopping=early_stopping,
            report_results=report_results,
            environment_definition=environment_definition,
        )

        self.last_stage: Union[str, int] = "root"
        """
        Current last stage of the pipeline.
        """

        for element in tasks:
            self.then(element)

    @staticmethod
    def _element_to_stage(element: PipelineElement) -> List[TaskElement]:
        if not isinstance(element, Collection):
            element = [element]
        if not isinstance(element, list):
            element = list(element)
        return element

    def then(self, element: PipelineElement) -> Pipeline:
        """
        Add a task or list of tasks as a separate stage to the end of the pipeline.

        :param element: a task or tuple of tasks to be added
        :return: self
        """
        element = self._element_to_stage(element)

        initial_stage = self.last_stage
        next_stage = self.last_stage + 1 if isinstance(self.last_stage, int) else 1
        self.graph.add_edges_from([(initial_stage, x) for x in element])
        self.graph.add_edges_from([(x, next_stage) for x in element])
        self.last_stage = next_stage

        return self

    def copy(self) -> Pipeline:
        """
        Return a copy of the pipeline.

        :return: a copy of the pipeline
        """
        pipeline = Pipeline(
            early_stopping=self.early_stopping,
            report_results=self.report_results,
            environment_definition=self.environment_definition,
        )

        pipeline.graph = self.graph.copy()
        return pipeline

    def __str__(self) -> str:
        successors = nx.dfs_successors(self.graph, "root")
        stages = {
            x: y for x, y in successors.items() if isinstance(x, int) or x == "root"
        }

        return f"Pipeline({self.name}): {stages}"

    def __repr__(self) -> str:
        return str(self)


class CyclePipeline(Pipeline):
    """
    CyclePipeline is a Pipeline that will be executed several times. All defined stages would be executed
    and then the execution would continue from the first stage again.
    """

    def __init__(
        self,
        cycles: Optional[int] = None,
        tasks: Collection[PipelineElement] = (),
        early_stopping: bool = True,
        report_results: bool = True,
        environment_definition: Optional[EnvironmentDefinition] = None,
    ):
        self.edge_params: Dict[str, Any] = {"type": "weak"}
        if cycles is not None:
            assert isinstance(cycles, int)
            if cycles <= 2:
                raise ValueError(
                    f"Number of cycles should be at least 2, current value: {cycles}"
                )
            self.edge_params["counter"] = cycles - 1

        super().__init__(
            tasks=tasks,
            early_stopping=early_stopping,
            report_results=report_results,
            environment_definition=environment_definition,
        )

        self.graph.add_edge("root", "root", **self.edge_params)

    def then(self, element: PipelineElement) -> Pipeline:
        """
        Add a task or list of tasks as a separate stage to the end of the pipeline.

        :param element: a task or tuple of tasks to be added
        :return: self
        """
        element = self._element_to_stage(element)

        initial_stage = self.last_stage
        if self.graph.has_edge(initial_stage, "root"):
            self.graph.remove_edge(initial_stage, "root")

        next_stage = self.last_stage + 1 if isinstance(self.last_stage, int) else 1
        self.graph.add_edges_from([(initial_stage, x) for x in element])
        self.graph.add_edges_from([(x, next_stage) for x in element])
        self.last_stage = next_stage
        self.graph.add_edge(next_stage, "root", **self.edge_params)

        return self
