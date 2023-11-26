import unittest

from netunicorn.base import ExecutionGraph, Task
from netunicorn.executor.executor import Executor, ExecutorState
from returns.pipeline import is_successful


class SuccessTask(Task):
    def run(self):
        return True


class FailTask(Task):
    def run(self):
        raise Exception("FailTask")


class TestEarlyStoppingAllSuccess(unittest.TestCase):
    def setUp(self):
        # root -> SuccessTask --traverse_on-> SuccessTask
        self.task1 = SuccessTask(name="dummy1")
        self.task2 = SuccessTask(name="dummy2")
        execution_graph = ExecutionGraph()
        execution_graph.graph.add_edge("root", self.task1)
        execution_graph.graph.add_edge(self.task1, self.task2)

        self.executor = Executor(gateway_endpoint="fake", heartbeat=False)
        execution_graph.report_results = False
        self.executor.execution_graph = execution_graph
        self.executor.state = ExecutorState.EXECUTING

    def test_traverse_not_set(self):
        self.executor()
        self.assertTrue(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertTrue(
                is_successful(self.executor.execution_graph_results.unwrap()[x][0])
            )

    def test_traverse_on_success(self):
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "success"

        self.executor()
        self.assertTrue(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertTrue(
                is_successful(self.executor.execution_graph_results.unwrap()[x][0])
            )

    def test_traverse_on_any(self):
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "any"

        self.executor()
        self.assertTrue(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertTrue(
                is_successful(self.executor.execution_graph_results.unwrap()[x][0])
            )

    def test_traverse_on_failure(self):
        # dummy1 exists, dummy2 does not
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "failure"

        self.executor()
        self.assertTrue(is_successful(self.executor.execution_graph_results))
        self.assertTrue(
            is_successful(self.executor.execution_graph_results.unwrap()["dummy1"][0])
        )
        self.assertTrue("dummy2" not in self.executor.execution_graph_results.unwrap())


class TestEarlyStoppingAllFail(unittest.TestCase):
    def setUp(self):
        # root -> FailTask --traverse_on-> FailTask
        self.task1 = FailTask(name="dummy1")
        self.task2 = FailTask(name="dummy2")
        execution_graph = ExecutionGraph()
        execution_graph.graph.add_edge("root", self.task1)
        execution_graph.graph.add_edge(self.task1, self.task2)

        self.executor = Executor(gateway_endpoint="fake", heartbeat=False)
        execution_graph.report_results = False
        self.executor.execution_graph = execution_graph
        self.executor.state = ExecutorState.EXECUTING

    def test_traverse_not_set(self):
        # dummy1 exists, dummy2 does not
        self.executor()
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        self.assertFalse(
            is_successful(self.executor.execution_graph_results.failure()["dummy1"][0])
        )
        self.assertTrue("dummy2" not in self.executor.execution_graph_results.failure())

    def test_traverse_on_success(self):
        # dummy1 exists, dummy2 does not
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "success"

        self.executor()
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        self.assertFalse(
            is_successful(self.executor.execution_graph_results.failure()["dummy1"][0])
        )
        self.assertTrue("dummy2" not in self.executor.execution_graph_results.failure())

    def test_traverse_on_any(self):
        # both dummy1 and dummy2 exist
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "any"

        self.executor()
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertFalse(
                is_successful(self.executor.execution_graph_results.failure()[x][0])
            )

    def test_traverse_on_failure(self):
        # both dummy1 and dummy2 exist
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "failure"

        self.executor()
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertFalse(
                is_successful(self.executor.execution_graph_results.failure()[x][0])
            )


class TestNoEarlyStoppingAllFail(unittest.TestCase):
    def setUp(self):
        # root -> FailTask --traverse_on-> FailTask
        self.task1 = FailTask(name="dummy1")
        self.task2 = FailTask(name="dummy2")
        execution_graph = ExecutionGraph()
        execution_graph.graph.add_edge("root", self.task1)
        execution_graph.graph.add_edge(self.task1, self.task2)

        self.executor = Executor(gateway_endpoint="fake", heartbeat=False)
        execution_graph.report_results = False
        execution_graph.early_stopping = False
        self.executor.execution_graph = execution_graph
        self.executor.state = ExecutorState.EXECUTING

    def test_traverse_on_success(self):
        # dummy1 exists, dummy2 does not
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "success"

        self.executor()
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        self.assertFalse(
            is_successful(self.executor.execution_graph_results.failure()["dummy1"][0])
        )
        self.assertTrue("dummy2" not in self.executor.execution_graph_results.failure())

    def _check_that_both_exist(self):
        self.executor()
        print(self.executor.execution_graph_results)
        self.assertFalse(is_successful(self.executor.execution_graph_results))
        for x in {"dummy1", "dummy2"}:
            self.assertFalse(
                is_successful(self.executor.execution_graph_results.failure()[x][0])
            )

    def test_traverse_on_not_set(self):
        # both dummy1 and dummy2 exist
        self._check_that_both_exist()

    def test_traverse_on_any(self):
        # both dummy1 and dummy2 exist
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "any"
        self._check_that_both_exist()

    def test_traverse_on_failure(self):
        # both dummy1 and dummy2 exist
        self.executor.execution_graph.graph[self.task1][self.task2][
            "traverse_on"
        ] = "failure"
        self._check_that_both_exist()


if __name__ == "__main__":
    unittest.main()
