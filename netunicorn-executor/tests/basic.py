import unittest

from netunicorn.base import CyclePipeline, ExecutionGraph, Pipeline, Task
from netunicorn.executor.executor import Executor, ExecutorState
from returns.pipeline import is_successful


class DummyTask(Task):
    def run(self):
        return 0


class TestExecutor(unittest.TestCase):
    @staticmethod
    def _get_executor(execution_graph: ExecutionGraph) -> Executor:
        executor = Executor(gateway_endpoint="fake", heartbeat=False)
        execution_graph.report_results = False
        executor.execution_graph = execution_graph
        executor.state = ExecutorState.EXECUTING
        return executor

    def test_dummy_pipeline(self):
        execution_graph = Pipeline().then(DummyTask(name="dummy"))
        executor = self._get_executor(execution_graph)
        executor()
        self.assertEqual(executor.state, ExecutorState.FINISHED)
        self.assertTrue(is_successful(executor.execution_graph_results))
        self.assertTrue(
            is_successful(executor.execution_graph_results.unwrap()["dummy"][0])
        )

    def test_cycle_pipeline(self):
        execution_graph = CyclePipeline(cycles=3).then(DummyTask(name="dummy"))
        executor = self._get_executor(execution_graph)
        executor()
        self.assertEqual(executor.state, ExecutorState.FINISHED)
        self.assertTrue(is_successful(executor.execution_graph_results))
        self.assertEqual(len(executor.execution_graph_results.unwrap()["dummy"]), 3)

    def test_execution_graph_1(self):
        execution_graph = ExecutionGraph()
        task1 = DummyTask(name="dummy1")
        task2 = DummyTask(name="dummy2")
        task3 = DummyTask(name="dummy3")
        task4 = DummyTask(name="dummy4")
        execution_graph.graph.add_edge("root", task1)
        execution_graph.graph.add_edge("root", task2)
        execution_graph.graph.add_edge(task1, task3)
        execution_graph.graph.add_edge(task2, task4)

        executor = self._get_executor(execution_graph)
        executor()

        self.assertTrue(is_successful(executor.execution_graph_results))
        for x in {"dummy1", "dummy2", "dummy3", "dummy4"}:
            self.assertTrue(
                is_successful(executor.execution_graph_results.unwrap()[x][0])
            )

    def test_execution_graph_2(self):
        execution_graph = ExecutionGraph()
        task1 = DummyTask(name="dummy1")
        task2 = DummyTask(name="dummy2")
        task3 = DummyTask(name="dummy3")
        task4 = DummyTask(name="dummy4")

        # root -> task1 -> task2
        #           v
        #         task3
        #          ^ v : 5 times
        #         task4
        execution_graph.graph.add_edge("root", task1)
        execution_graph.graph.add_edge(task1, task2)
        execution_graph.graph.add_edge(task1, task3)
        execution_graph.graph.add_edge(task3, task4)
        execution_graph.graph.add_edge(task4, task3, type="weak", counter=4)

        executor = self._get_executor(execution_graph)
        executor()

        self.assertTrue(is_successful(executor.execution_graph_results))
        for x in {"dummy1", "dummy2", "dummy3", "dummy4"}:
            results_list = executor.execution_graph_results.unwrap()[x]
            self.assertTrue(all(is_successful(result) for result in results_list))

        for x in {"dummy3", "dummy4"}:
            results_list = executor.execution_graph_results.unwrap()[x]
            self.assertEqual(len(results_list), 5)
