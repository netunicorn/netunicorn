"""
Abstraction for an execution graph that contains tasks and their order.
"""

from __future__ import annotations

import uuid
from typing import Optional

import networkx as nx

from .environment_definitions import DockerImage, EnvironmentDefinition


class ExecutionGraph:
    """
    ExecutionGraph is a class that allows you to flexibly define a graph of tasks and their order.
    It has the next rules:
    | 1. Execution graph is a directed graph.
    | 2. Execution graph always starts with a node "root" (this node is automatically added in the new graph during initialization).
    | 3. Any node of type TaskDispather would be dispatched to Task. Any node of type Task would be executed. Any nodes of other types would not be executed but would be treated as synchronization points.
    | 4. Number of components in the graph must be 1, the graph should be weakly connected, and all nodes should be accessible from the root node.
    | 5. Any edge can have attribute "counter" with integer value. This value would be used to determine how many times this edge should be traversed. If this attribute is not present, then edge would be traversed infinitely. You can use this attribute to implement finite loops in the graph.

    :param early_stopping: If True, then the execution of the graph would be stopped if any task fails. If False, then the execution of the graph would be continued even if some tasks fail.
    :param report_results: If True, then the executor would connect core services to report execution results in the end.
    :param environment_definition: environment definition for the execution graph
    """

    def __init__(
        self,
        early_stopping: bool = True,
        report_results: bool = True,
        environment_definition: Optional[EnvironmentDefinition] = None,
    ):
        self.name: str = str(uuid.uuid4())
        """
        Execution Graph name.
        """

        self.early_stopping: bool = early_stopping
        """
        Whether to stop executing tasks after first failure.
        """

        self.report_results: bool = report_results
        """
        Whether executor should connect core services to report execution results in the end.
        """

        self.environment_definition: EnvironmentDefinition = (
            environment_definition or DockerImage()
        )
        """
        Environment definition for the execution graph.
        """

        self.graph = nx.DiGraph()
        """
        Graph of tasks and their order.
        """

        self.graph.add_node("root")

    @staticmethod
    def is_execution_graph_valid(obj: ExecutionGraph) -> bool:
        """
        Validates execution graph according to the ExecutionGraph rules.

        :return: True if execution graph is valid, raises an exception otherwise
        """

        if not isinstance(obj, ExecutionGraph):
            raise TypeError("Execution graph must be a directed graph")

        graph = obj.graph
        if not nx.is_weakly_connected(graph):
            raise ValueError(
                "Execution graph must be a weakly connected directed graph"
            )

        if not graph.has_node("root"):
            raise ValueError("Execution graph must have a root node")

        successors = set(nx.dfs_postorder_nodes(graph, "root"))
        if diff := set(graph.nodes).difference(successors):
            raise ValueError(
                f"All tasks must be accessible from the root node. Inaccessible nodes: {diff}"
            )

        return True

    def __copy__(self) -> ExecutionGraph:
        graph = ExecutionGraph(
            early_stopping=self.early_stopping,
            report_results=self.report_results,
            environment_definition=self.environment_definition,
        )
        graph.graph = self.graph.copy()
        return graph

    def __str__(self) -> str:
        return f"ExecutionGraph(name={self.name}, {self.graph.__str__()})"

    def __repr__(self) -> str:
        return self.__str__()
