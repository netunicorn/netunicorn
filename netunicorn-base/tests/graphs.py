import unittest
import networkx as nx

from netunicorn.base import Task, Pipeline, CyclePipeline, ExecutionGraph


class DummyTask(Task):
    def run(self):
        return 0


class TestValidAndInvalidGraphs(unittest.TestCase):
    def test_dummy(self):
        graph = ExecutionGraph()
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

    def test_pipelines(self):
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(Pipeline()))

        graph = (
            Pipeline()
            .then(DummyTask())
            .then([DummyTask(), DummyTask(), DummyTask()])
            .then([DummyTask(), DummyTask()])
            .then(DummyTask())
        )
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

    def test_cycle_pipelines(self):
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(CyclePipeline()))
        self.assertTrue(
            ExecutionGraph.is_execution_graph_valid(CyclePipeline(cycles=100))
        )

        graph = (
            CyclePipeline()
            .then(DummyTask())
            .then([DummyTask(), DummyTask(), DummyTask()])
            .then([DummyTask(), DummyTask()])
            .then(DummyTask())
        )
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

        graph = (
            CyclePipeline(cycles=100)
            .then(DummyTask())
            .then([DummyTask(), DummyTask(), DummyTask()])
            .then([DummyTask(), DummyTask()])
            .then(DummyTask())
        )
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

    def test_invalid_graphs_0(self):
        # wrong types
        graphs = [nx.Graph(), nx.MultiGraph(), nx.MultiDiGraph()]
        for x in graphs:
            with self.assertRaises(Exception):
                ExecutionGraph.is_execution_graph_valid(x)  # type: ignore

        # not connected
        graph = ExecutionGraph()
        graph.graph.add_node("a")
        with self.assertRaises(Exception):
            ExecutionGraph.is_execution_graph_valid(graph)

        # no root
        graph = ExecutionGraph()
        graph.graph.remove_node("root")
        with self.assertRaises(Exception):
            ExecutionGraph.is_execution_graph_valid(graph)

        # not all nodes are accessible from root
        graph = ExecutionGraph()
        graph.graph.add_node("a")
        graph.graph.add_edge("a", "root")
        with self.assertRaises(Exception):
            ExecutionGraph.is_execution_graph_valid(graph)

        # cycles without weak links
        graph = ExecutionGraph()
        graph.graph.add_edge("root", "root")
        with self.assertRaises(Exception):
            ExecutionGraph.is_execution_graph_valid(graph)

        graph = ExecutionGraph()
        graph.graph.add_edge("root", "a")
        graph.graph.add_edge("a", "b")
        graph.graph.add_edge("b", "a")
        with self.assertRaises(Exception):
            ExecutionGraph.is_execution_graph_valid(graph)

    def test_valid_graphs_0(self):
        # not very logical, but valid
        graph = ExecutionGraph()
        graph.graph.add_edges_from(
            [("root", "a"), ("a", "b"), ("b", "c"), ("c", "d"), ("a", "d")]
        )
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

        # cycles
        graph = ExecutionGraph()
        graph.graph.add_edges_from(
            [("root", "a"), ("a", "b"), ("a", "c"), ("b", "d"), ("d", "e"), ("c", "e")]
        )
        graph.graph.add_edges_from([("e", "b"), ("e", "c")], type="weak")
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

        # complicated
        graph = ExecutionGraph()
        graph.graph.add_edges_from(
            [
                ("root", "a"),
                ("root", "b"),
                ("root", "c"),
                ("a", "e"),
                ("b", "d"),
                ("c", "d"),
                ("d", "e"),
            ]
        )
        graph.graph.add_edges_from([("e", "d"), ("e", "c")], type="weak")
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))

        # cycle on a stick
        graph = ExecutionGraph()
        graph.graph.add_edges_from(
            [("root", "a"), ("a", "b"), ("b", "c"), ("c", "d"), ("b", "e"), ("e", "f")]
        )
        graph.graph.add_edge("f", "e", type="weak")
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(graph))


if __name__ == "__main__":
    unittest.main()
