import unittest

import networkx as nx

from netunicorn.base import CyclePipeline, ExecutionGraph, Pipeline, Task


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
            with self.assertRaises(ValueError):
                eg = ExecutionGraph()
                eg.graph = x
                ExecutionGraph.is_execution_graph_valid(eg)

        # not connected
        graph = ExecutionGraph()
        graph.graph.add_node("a")
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(graph)

        # no root
        graph = ExecutionGraph()
        graph.graph.remove_node("root")
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(graph)

        # not all nodes are accessible from root
        graph = ExecutionGraph()
        graph.graph.add_node("a")
        graph.graph.add_edge("a", "root")
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(graph)

        # cycles without weak links
        graph = ExecutionGraph()
        graph.graph.add_edge("root", "root")
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(graph)

        graph = ExecutionGraph()
        graph.graph.add_edge("root", "a")
        graph.graph.add_edge("a", "b")
        graph.graph.add_edge("b", "a")
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(graph)

        graph = ExecutionGraph()
        graph.graph.add_edge("root", "a")
        graph.graph.add_edge("b", "a")
        graph.graph.add_edge("a", "b", type="weak")
        with self.assertRaises(ValueError):
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

    def test_invalid_traverse_on_values(self):
        ex_graph = ExecutionGraph()
        task = DummyTask()
        task2 = DummyTask()
        ex_graph.graph.add_edges_from([("root", task), (task, task2)])
        ex_graph.graph[task][task2]["traverse_on"] = "invalid"
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(ex_graph)

    def test_traverse_on_from_sync_node(self):
        # traverse_on attribute is not allowed for edges from sync nodes
        ex_graph = ExecutionGraph()
        task = DummyTask()
        ex_graph.graph.add_edges_from([("root", "sync"), ("sync", task)])
        ex_graph.graph["sync"][task]["traverse_on"] = "any"
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(ex_graph)

    def test_valid_traverse_on(self):
        ex_graph = ExecutionGraph()
        task1 = DummyTask()
        task2 = DummyTask()
        task3 = DummyTask()
        task4 = DummyTask()
        ex_graph.graph.add_edges_from(
            [
                ("root", task1),
                ("root", task2),
                (task1, task3),
                (task2, task4),
            ]
        )
        ex_graph.graph[task2][task4]["traverse_on"] = "any"
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(ex_graph))

    def test_invalid_counters(self):
        exec_graph = ExecutionGraph()
        exec_graph.graph.add_edge("root", "a")
        exec_graph.graph.add_edge("a", "b", counter=0)
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(exec_graph)

        exec_graph.graph["a"]["b"]["counter"] = -1
        with self.assertRaises(ValueError):
            ExecutionGraph.is_execution_graph_valid(exec_graph)

    def test_valid_counters(self):
        exec_graph = ExecutionGraph()
        exec_graph.graph.add_edge("root", "a")
        exec_graph.graph.add_edge("a", "root", counter=5, type="weak")
        self.assertTrue(ExecutionGraph.is_execution_graph_valid(exec_graph))


if __name__ == "__main__":
    unittest.main()
