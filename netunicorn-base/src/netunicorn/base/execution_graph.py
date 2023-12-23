"""
Abstraction for an execution graph that contains tasks and their order.
"""

from __future__ import annotations

import uuid
from typing import Optional

import networkx as nx

from .environment_definitions import DockerImage, EnvironmentDefinition
from .task import Task, TaskDispatcher


class ExecutionGraph:
    """
    ExecutionGraph is a class that allows you to flexibly define a graph of tasks and their order.
    It has the next rules:

    | 1. Execution graph is a directed graph.
    | 2. Execution graph always starts with a node "root" (this node is automatically added in the new graph during initialization).
    | 3. Any node of type TaskDispather would be dispatched to Task. Any node of type Task would be executed. Any nodes of other types would not be executed but would be treated as synchronization points.
    | 4. Number of components in the graph must be 1, the graph should be weakly connected, and all nodes should be accessible from the root node.
    | 5. Any edge have either "strong" or "weak" type. If no type provided, it's a "strong" edge.
    Type is provided as an attribute "type" with value "strong" or "weak".
    Executor will not treat incoming "weak" edges as requirements for the execution of the task, but will traverse them to start executing next tasks.
    "Weak" edges are required for cycle dependencies to avoid deadlocks.
    You can consider weak links as links for defining the execution flow, and strong links to define both execution flow and prerequisites.

    | 6. Any edge can have attribute "counter" with integer value. This value would be used to determine how many times this edge should be traversed. If this attribute is not present, then edge would be traversed infinitely. You can use this attribute to implement finite loops in the graph.

    | 7. Any edge can have attribute "traverse_on" with either string value "success", "failure", or "any". This attribute controls whether executor will traverse this edge on success or failure of the task. If this attribute is not present, the executor will obey the usual rules considering the "early_stopping" parameter (trat all edges as "success" for "early_stopping=True" or "any" for "early_stopping=False"). If this attribute is present, then the executor will traverse this edge only if the task was executed successfully ("success"), failed ("failure"), or in any case ("any"). The next rules apply:
    If "early_stopping" is True, all edges are treated as having "traverse_on" attribute set to "success". Setting the "traverse_on" attribute to "failure" would make the executor to traverse this edge in case of the task failure and will not break the execution of the graph. Also, setting the "traverse_on" attribute to "any" would make executor to traverse this edge in case of the task failure or success and will not break the execution of the graph.
    If "early_stopping" is False, all edges are treated as having "traverse_on" attribute set to "any". Setting this attribute to "success" or "failure" would make the executor to traverse this edge only in case of the task success or failure respectively.

    :param early_stopping: If True, then the execution of the graph would be stopped if any task fails. If False, then the execution of the graph would be continued even if some tasks fail. In both cases, "traverse_on" attribute of the edges could be used to control the traversal of the graph.
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
        Whether to stop executing tasks after a first failure.
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

        self.override_graph_validation = False
        """
        Disable graph validation. Executor and other components will not validate the graph before execution.
        """

        self.graph.add_node("root")

    @staticmethod
    def is_execution_graph_valid(obj: ExecutionGraph) -> bool:
        """
        Validates execution graph according to the ExecutionGraph rules.

        :return: True if execution graph is valid, raises an exception otherwise
        """

        if obj.override_graph_validation:
            return True

        if not isinstance(obj, ExecutionGraph):
            raise ValueError("The object is not an instance of ExecutionGraph")

        graph = obj.graph

        if not isinstance(graph, nx.DiGraph) or isinstance(graph, nx.MultiDiGraph):
            raise ValueError("Execution graph must be a directed graph (DiGraph)")

        if not graph.has_node("root"):
            raise ValueError("Execution graph must have a root node")

        if not nx.is_weakly_connected(graph):
            raise ValueError(
                "Execution graph must be a weakly connected directed graph"
            )

        successors = set(nx.dfs_postorder_nodes(graph, "root"))
        if diff := set(graph.nodes).difference(successors):
            raise ValueError(
                f"All tasks must be accessible from the root node. Inaccessible nodes: {diff}"
            )

        # if remove all weak links, the graph should be acyclic
        graph_copy = graph.copy()
        graph_copy.remove_edges_from(
            [
                (u, v)
                for u, v, d in graph_copy.edges(data=True)
                if d.get("type", "strong") == "weak"
            ]
        )
        if not nx.is_directed_acyclic_graph(graph_copy):
            raise ValueError(
                "Execution graph must be acyclic after removing all weak links. Otherwise your cycles will introduce deadlocks."
            )
        successors = set(nx.dfs_postorder_nodes(graph_copy, "root"))
        if diff := set(graph_copy.nodes).difference(successors):
            raise ValueError(
                f"After removing weak links, all nodes should be accessible from the root. Inaccessible nodes: {diff}"
            )

        # "counter" attribute on each edge should be positive number
        for u, v, d in graph.edges(data=True):
            if "counter" in d:
                try:
                    counter = int(d["counter"])
                except ValueError:
                    raise ValueError(
                        f"Edge ({u}, {v}) has attribute 'counter' with value '{d['counter']}'. "
                        f"This value should be a valid integer."
                    )

                if counter <= 0:
                    raise ValueError(
                        f"Edge ({u}, {v}) has attribute 'counter' with value '{d['counter']}'. "
                        f"This value should be a positive integer."
                    )

        # all edges having "traverse_on" attribute should have value "success", "failure", or "any"
        for u, v, d in graph.edges(data=True):
            if "traverse_on" in d:
                traverse_on = d["traverse_on"]
                if traverse_on not in ["success", "failure", "any"]:
                    raise ValueError(
                        f"Edge ({u}, {v}) has attribute 'traverse_on' with value '{traverse_on}'. This value should be either 'success', 'failure', or 'any'."
                    )

        # no edges starting at synchronization points (non-Task) points should have "traverse_on" attribute
        for u, v, d in graph.edges(data=True):
            if (
                not (isinstance(u, Task) or isinstance(u, TaskDispatcher))
                and "traverse_on" in d
            ):
                raise ValueError(
                    f"Edge ({u}, {v}) has attribute 'traverse_on' with value '{d['traverse_on']}'. This attribute should not be present for edges starting at synchronization points (non-Task nodes)."
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

    def __hash__(self) -> int:
        return hash(self.name)

    def __repr__(self) -> str:
        return self.__str__()

    # graph visualization
    @staticmethod
    def _get_edge_label_string(edge: dict) -> str:  # type: ignore[type-arg]
        values = [
            f"'{key}': {value}" for key, value in edge.items() if value is not None
        ]

        label = ", ".join(values)
        return f"{{{label}}}" if values else ""

    def draw(self, nx_layout_function=nx.shell_layout) -> None:  # type: ignore[no-untyped-def]
        """
        Draw execution graph using networkx library.

        :param nx_layout_function: networkx layout function to use for drawing (from networkx.drawing.layout)
        :return: None
        """

        node_labels = {
            task: task.name if hasattr(task, "name") else task
            for task in self.graph.nodes
        }

        edge_labels = {
            (u, v): self._get_edge_label_string(d)
            for u, v, d in self.graph.edges(data=True)
        }

        layout = nx_layout_function(self.graph)
        nx.draw(self.graph, layout)
        nx.draw_networkx_labels(self.graph, layout, labels=node_labels)
        nx.draw_networkx_edge_labels(self.graph, layout, edge_labels=edge_labels)

        return
