import unittest

import networkx as nx
from netunicorn.base import CyclePipeline, ExecutionGraph, Pipeline, Task


class DummyTask(Task):
    def run(self):
        return 0


class TestCyclePipeline(unittest.TestCase):
    def test_invalid_1(self):
        with self.assertRaises(ValueError):
            CyclePipeline(cycles=1)

    def test_valid_1(self):
        pipeline = CyclePipeline(cycles=3).then(DummyTask())
        cycling_edge_params = list(pipeline.graph.edges(data=True))[-1][2]
        self.assertEqual(cycling_edge_params["counter"], 2)
        self.assertEqual(cycling_edge_params["type"], "weak")
