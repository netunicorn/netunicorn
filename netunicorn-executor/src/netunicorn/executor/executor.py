from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from asyncio import CancelledError
from base64 import b64decode, b64encode
from collections import defaultdict
from copy import deepcopy
from multiprocessing import Process, Queue
from typing import Any, Dict, List, Optional, Set, Type, Union

import cloudpickle
import requests as req
import requests.exceptions
from netunicorn.base.execution_graph import ExecutionGraph
from netunicorn.base.task import Task, TaskDispatcher
from netunicorn.base.types import ExecutionGraphResult, ExecutorState
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success
from typing_extensions import TypedDict

from .utils import safe

RunningTasksItem = TypedDict(
    "RunningTasksItem", {"process": Process, "queue": "Queue[bytes]"}
)
FinishedTasksItem = TypedDict(
    "FinishedTasksItem",
    {"process": Optional[Process], "queue": Optional["Queue[bytes]"]},
)


class Executor:
    def __init__(
        self,
        executor_id: Optional[str] = None,
        gateway_endpoint: Optional[str] = None,
        experiment_id: Optional[str] = None,
        heartbeat: bool = True,
    ):
        # load up our own ID and the local communicator info
        self.gateway_endpoint: str = (
            gateway_endpoint or os.environ["NETUNICORN_GATEWAY_ENDPOINT"]
        )
        if self.gateway_endpoint[-1] == "/":
            self.gateway_endpoint = self.gateway_endpoint[:-1]

        self.executor_id: str = (
            executor_id or os.environ.get("NETUNICORN_EXECUTOR_ID") or "Unknown"
        )
        self.experiment_id: str = (
            experiment_id or os.environ.get("NETUNICORN_EXPERIMENT_ID") or "Unknown"
        )

        self.logfile_name = f"executor_{self.executor_id}.log"
        self.print_file = open(self.logfile_name, "at")

        self.heartbeat_flag = heartbeat
        self.heartbeat_seconds = int(
            os.environ.get("NETUNICORN_EXECUTOR_HEARTBEAT_SECONDS") or 30
        )

        logging.basicConfig()
        self.logger = self.create_logger()
        self.logger.info(
            f"Parsed configuration: Gateway located on {self.gateway_endpoint}"
        )
        self.logger.info(f"Current directory: {os.getcwd()}")

        # increasing timeout in secs to wait between network requests
        self.backoff_func = (
            5 * x for x in range(10)
        )  # limit to 225 secs total, then StopIteration Exception

        self.execution_graph: Optional[ExecutionGraph] = None
        self.step_results: ExecutionGraphResult = defaultdict(list)
        self.execution_graph_results: Optional[
            Result[ExecutionGraphResult, ExecutionGraphResult]
        ] = None
        self.state = ExecutorState.LOOKING_FOR_EXECUTION_GRAPH

    async def heartbeat(self) -> None:
        while self.state == ExecutorState.EXECUTING:
            try:
                await asyncio.sleep(self.heartbeat_seconds)

                with open(self.logfile_name, "rt") as f:
                    current_log = f.readlines()
                results = cloudpickle.dumps([Success(self.step_results), current_log])
                results_data = b64encode(results).decode()

                req.post(
                    f"{self.gateway_endpoint}/api/v1/executor/result/",
                    json={
                        "executor_id": self.executor_id,
                        "results": results_data,
                        "state": self.state.value,
                    },
                    timeout=30,
                )
            except Exception as e:
                self.logger.exception(e)
            except CancelledError:
                return

    def create_logger(self) -> logging.Logger:
        logger = logging.getLogger(f"executor_{self.executor_id}")
        logger.addHandler(logging.FileHandler(self.logfile_name))
        logger.setLevel(logging.DEBUG)
        return logger

    def __call__(self) -> None:
        """
        This method is the main loop of the executor.
        :return: None
        """
        while True:
            try:
                if self.state == ExecutorState.LOOKING_FOR_EXECUTION_GRAPH:
                    self.request_execution_graph()
                elif self.state == ExecutorState.EXECUTING:
                    asyncio.run(self.execute())
                elif self.state == ExecutorState.REPORTING:
                    self.report_results()
                elif self.state == ExecutorState.FINISHED:
                    self.print_file.close()
                    return
            except Exception as e:
                self.logger.exception(e)
                self.logger.critical("Failed to execute the graph. Shutting down.")
                self.state = ExecutorState.FINISHED
                break

        # if we break the cycle with an exception, we'll try to report the results
        self.report_results()
        self.print_file.close()

    def request_execution_graph(self) -> None:
        """
        This method tries to look for an execution graph locally to execute, and if not found then asks the master for it
        :return: None
        """

        if self.execution_graph is not None:
            self.logger.error(
                "request_execution_graph is called, but self.execution_graph is already set, executing."
            )
            self.state = ExecutorState.EXECUTING
            return

        execution_graph_filename = f"netunicorn.execution_graph"
        if os.path.exists(execution_graph_filename):
            with open(execution_graph_filename, "rb") as f:
                self.execution_graph = cloudpickle.load(f)
                self.logger.info("Execution graph loaded from a local file, executing.")
                self.state = ExecutorState.EXECUTING
                return

        try:
            result = req.get(
                f"{self.gateway_endpoint}/api/v1/executor/execution_graph?executor_id={self.executor_id}",
                timeout=30,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.info(f"Exception while requesting an execution graph: {e} ")
            time.sleep(next(self.backoff_func))
            return

        if result.status_code == 200:
            execution_graph = b64decode(result.content)
            self.execution_graph = cloudpickle.loads(execution_graph)
            self.state = ExecutorState.EXECUTING
            self.logger.info("Successfully received the execution graph.")
        else:
            self.logger.info(
                f"Failed to receive the execution graph. Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
            )

    def execute_task(
        self, serialized_task: bytes, result_queue: "Queue[bytes]"
    ) -> None:
        self.std_redirection()
        task = cloudpickle.loads(serialized_task)
        result: Result[Any, Any] = safe(task.run)()
        result_queue.put(cloudpickle.dumps(result))

    def std_redirection(self, *args: Any) -> None:
        _ = args
        sys.stdout = self.print_file
        sys.stderr = self.print_file

    def add_successors_to_waiting_tasks(
        self,
        waiting_tasks: List[Union[Any, Task]],
        current_task: Union[Any, Task],
        task_execution_successful: Optional[bool],
    ) -> bool:
        """
        This method takes a current task and a list of waiting tasks, and adds successors of the current task to the waiting tasks
        This method considers "traverse_on" attribute of edges, current "early_stopping" flag, and result of the current task

        :returns: True if the execution should be stopped, False otherwise
        """

        if not self.execution_graph:
            error = "No execution graph to execute. Incorrect function call."
            self.logger.error(error)
            raise Exception(error)

        any_edges_with_traverse_on_failure_or_any = False
        edges_to_delete = []
        for successor in self.execution_graph.graph.successors(current_task):
            edge = self.execution_graph.graph.edges[current_task, successor]

            # current possible values: None, "success", "failure", "any"
            traverse_on = edge.get("traverse_on", None)
            if traverse_on is None:
                traverse_on = (
                    "success" if self.execution_graph.early_stopping else "any"
                )
            if traverse_on not in {"success", "failure", "any"}:
                # we validated the graph before, so this should never happen
                error_text = f"Invalid traverse_on attribute value {traverse_on} for edge {current_task} -> {successor}"
                self.logger.error(error_text)
                raise ValueError(error_text)

            if (
                task_execution_successful is None
                or traverse_on == "any"
                or (traverse_on == "success" and task_execution_successful)
                or (traverse_on == "failure" and not task_execution_successful)
            ):
                any_edges_with_traverse_on_failure_or_any = True
                waiting_tasks.append(successor)
            else:
                continue

            counter = self.execution_graph.graph.edges[current_task, successor].get(
                "counter", None
            )
            if counter is not None:
                counter -= 1
                self.execution_graph.graph.edges[current_task, successor][
                    "counter"
                ] = counter
                if counter <= 0:
                    edges_to_delete.append((current_task, successor))

        for edge in edges_to_delete:
            self.execution_graph.graph.remove_edge(*edge)
            self.logger.info(f"Removed edge {edge[0]} -> {edge[1]}")

        if (
            task_execution_successful is False
            and self.execution_graph.early_stopping is True
            and not any_edges_with_traverse_on_failure_or_any
        ):
            # that means that task failed early_stopping is on
            #  and there are no edges to successors with traverse_on == "any" or "failure"
            #  to continue execution
            #  so we should stop execution
            return True

        return False

    def _verify_no_task_dispatchers(self) -> None:
        """
        This method verifies that there are no task dispatchers in the execution graph.
        """
        if self.execution_graph is None:
            raise ValueError("No execution graph to execute.")

        for node in self.execution_graph.graph.nodes:
            if isinstance(node, TaskDispatcher):
                raise ValueError(
                    f"Node of the type TaskDispatcher {node.name} is not supported in the execution graph."
                )

    async def execute(self) -> None:
        """
        This method executes the execution graph.
        """

        if self.heartbeat_flag:
            asyncio.create_task(self.heartbeat())

        if not self.execution_graph:
            self.logger.error("No execution graph to execute.")
            self.execution_graph_results = Failure(self.step_results)
            self.state = ExecutorState.REPORTING
            return

        try:
            ExecutionGraph.is_execution_graph_valid(self.execution_graph)
        except Exception as e:
            self.logger.error("The provided execution graph is not valid.")
            self.logger.exception(e)
            self.execution_graph_results = Failure(self.step_results)
            self.state = ExecutorState.REPORTING
            return

        try:
            self._verify_no_task_dispatchers()
        except ValueError as e:
            self.logger.error(e)
            self.execution_graph_results = Failure(self.step_results)
            self.state = ExecutorState.REPORTING
            return

        resulting_type: Type[
            Result[ExecutionGraphResult, ExecutionGraphResult]
        ] = Success

        waiting_tasks: Set[Union[Any, Task]] = {"root"}
        running_tasks: Dict[Task, RunningTasksItem] = {}
        finished_tasks: Dict[Union[Task, str], FinishedTasksItem] = {}

        stop_execution = False

        while not stop_execution:
            tasks_to_delete = []
            tasks_to_add: List[Union[Any, Task]] = []
            tasks_processed = False
            if not waiting_tasks and not running_tasks:
                break

            # check running tasks: if any of them finished, then we should remove them from the running tasks,
            #  process their results, add it to finished for requirements check, and add descendants to the waiting tasks
            for task in running_tasks:
                if running_tasks[task]["process"].is_alive():
                    continue

                running_tasks[task]["process"].join()
                tasks_processed = True

                # sanity checks
                if running_tasks[task]["process"].exitcode != 0:
                    # unconditionally stop because process should always finish with exit code 0
                    resulting_text = f"Execution process of the task {task.name} failed with the exit code {running_tasks[task]['process'].exitcode}"
                    self.logger.error(resulting_text)
                    self.step_results[task.name].append(Failure(resulting_text))
                    stop_execution = True
                    break
                if running_tasks[task]["queue"].empty():
                    # unconditionally fail because process should always return results in the queue
                    resulting_text = f"Execution process of the task {task.name} failed to return results into a queue"
                    self.logger.error(resulting_text)
                    self.step_results[task.name].append(Failure(resulting_text))
                    stop_execution = True
                    break

                result = cloudpickle.loads(running_tasks[task]["queue"].get())
                self.step_results[task.name].append(result)
                if not is_successful(result):
                    resulting_type = Failure

                finished_tasks[task] = {
                    "process": running_tasks[task]["process"],
                    "queue": running_tasks[task]["queue"],
                }

                tasks_to_delete.append(task)

                # successor "traverse_on" attributes and current early_stopping flag define whether we should stop execution
                stop_execution = self.add_successors_to_waiting_tasks(
                    tasks_to_add, task, is_successful(result)
                )
                if stop_execution:
                    break

            for x in tasks_to_delete:
                del running_tasks[x]
            for x in tasks_to_add:
                waiting_tasks.add(x)
            tasks_to_delete = []
            tasks_to_add = []

            # for each task in waiting: if all their ancestors connected via strong links finished, start the task and add to running
            for task in waiting_tasks:
                if all(
                    ancestor in finished_tasks
                    for ancestor in self.execution_graph.graph.predecessors(task)
                    if self.execution_graph.graph.edges[ancestor, task].get(
                        "type", "strong"
                    )
                    != "weak"
                ):
                    tasks_to_delete.append(task)
                    tasks_processed = True

                    # if type - Task -> start and add to running, ...
                    if isinstance(task, Task):
                        task.previous_steps = deepcopy(self.step_results)
                        serialized_task = cloudpickle.dumps(task)

                        queue: "Queue[bytes]" = Queue()
                        running_tasks[task] = {
                            "queue": queue,
                            "process": Process(
                                target=self.execute_task, args=(serialized_task, queue)
                            ),
                        }
                        running_tasks[task]["process"].start()
                    else:
                        # ...otherwise just synchronization
                        finished_tasks[task] = {"process": None, "queue": None}
                        self.add_successors_to_waiting_tasks(tasks_to_add, task, None)

            for x in tasks_to_delete:
                waiting_tasks.remove(x)
            for x in tasks_to_add:
                waiting_tasks.add(x)

            if not running_tasks and waiting_tasks and not tasks_processed:
                # deadlock?
                self.logger.error(
                    f"Possible deadlock detected, exiting. Waiting tasks: {waiting_tasks}"
                )
                self.execution_graph_results = Failure(self.step_results)
                break

            if not tasks_processed:
                await asyncio.sleep(1.0)

        # set flag that the execution is finished
        self.logger.info("Execution is finished, start reporting results.")
        self.state = ExecutorState.REPORTING
        self.execution_graph_results = resulting_type(self.step_results)

    def report_results(self) -> None:
        """
        This method reports the results to the communicator.
        """
        if (
            isinstance(self.execution_graph, ExecutionGraph)
            and not self.execution_graph.report_results
        ):
            self.logger.info(
                "Skipping reporting results due to execution graph setting."
            )
            self.state = ExecutorState.FINISHED
            return

        with open(self.logfile_name, "rt") as f:
            current_log = f.readlines()

        try:
            results = cloudpickle.dumps([self.execution_graph_results, current_log])
        except Exception as e:
            results = cloudpickle.dumps([e, current_log])
        results_data = b64encode(results).decode()
        try:
            result = req.post(
                f"{self.gateway_endpoint}/api/v1/executor/result",
                json={
                    "executor_id": self.executor_id,
                    "results": results_data,
                    "state": self.state.value,
                },
                timeout=30,
            )
            self.logger.info("Successfully reported results.")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.info(f"Exception while reporting results: {e} ")
            time.sleep(next(self.backoff_func))
            return

        if result.status_code == 200:
            self.state = ExecutorState.FINISHED
        else:
            self.logger.warning(
                f"Failed to report results. Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
            )


# for backward compatibility
PipelineExecutor = Executor


def get_local_executor(execution_graph: ExecutionGraph) -> Executor:
    """
    Returns an executor configured for the local execution.

    :param execution_graph: Execution graph to execute
    :return: configured executor
    """

    executor = Executor(
        executor_id="local",
        gateway_endpoint="fake",
        experiment_id="local",
        heartbeat=False,
    )
    execution_graph.report_results = False
    executor.execution_graph = execution_graph
    executor.state = ExecutorState.EXECUTING
    return executor


if __name__ == "__main__":
    Executor().__call__()
