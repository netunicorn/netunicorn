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
from typing import Any, Dict, Optional, Set, Type, Union

import cloudpickle
import requests as req
import requests.exceptions
from netunicorn.base.execution_graph import ExecutionGraph
from netunicorn.base.task import Task
from netunicorn.base.types import ExecutionGraphResult, ExecutorState
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success
from typing_extensions import TypedDict

from .utils import safe

RunningTasksItem = TypedDict(
    "RunningTasksItem", {"process": Process, "queue": Queue[bytes]}
)
FinishedTasksItem = TypedDict(
    "FinishedTasksItem", {"process": Optional[Process], "queue": Optional[Queue[bytes]]}
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

        logging.basicConfig()
        self.logger = self.create_logger()
        self.logger.info(
            f"Parsed configuration: Gateway located on {self.gateway_endpoint}"
        )
        self.logger.info(f"Current directory: {os.getcwd()}")

        # increasing timeout in secs to wait between network requests
        self.backoff_func = (
            0.5 * x for x in range(75)
        )  # limit to 1425 secs total, then StopIteration Exception

        self.execution_graph: Optional[ExecutionGraph] = None
        self.step_results: ExecutionGraphResult = defaultdict(list)
        self.execution_graph_results: Optional[
            Result[ExecutionGraphResult, ExecutionGraphResult]
        ] = None
        self.state = ExecutorState.LOOKING_FOR_EXECUTION_GRAPH

    async def heartbeat(self) -> None:
        while self.state == ExecutorState.EXECUTING:
            try:
                await asyncio.sleep(30)
                req.post(
                    f"{self.gateway_endpoint}/api/v1/executor/heartbeat/{self.executor_id}"
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
                    return
            except Exception as e:
                self.logger.exception(e)
                self.logger.critical("Failed to execute the graph. Shutting down.")
                self.state = ExecutorState.FINISHED
                break

        # if we break the cycle with an exception, we'll try to report the results
        self.report_results()

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

    def execute_task(self, serialized_task: bytes, result_queue: Queue[bytes]) -> None:
        self.std_redirection()
        task = cloudpickle.loads(serialized_task)
        result: Result[Any, Any] = safe(task.run)()
        result_queue.put(cloudpickle.dumps(result))

    def std_redirection(self, *args: Any) -> None:
        _ = args
        sys.stdout = self.print_file
        sys.stderr = self.print_file

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

        resulting_type: Type[
            Result[ExecutionGraphResult, ExecutionGraphResult]
        ] = Success

        waiting_tasks: Set[Union[Any, Task]] = set("root")
        running_tasks: Dict[Task, RunningTasksItem] = {}
        finished_tasks: Dict[Union[Task, str], FinishedTasksItem] = {}

        stop_execution = False

        while (
            self.execution_graph.early_stopping and not stop_execution
        ) or not self.execution_graph.early_stopping:
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
                    resulting_text = f"Task {task.name} failed with exit code {running_tasks[task]['process'].exitcode}"
                    self.logger.error(resulting_text)
                    self.step_results[task.name].append(Failure(resulting_text))
                    stop_execution = True
                elif running_tasks[task]["queue"].empty():
                    resulting_text = f"Task {task.name} failed with empty queue"
                    self.logger.error(resulting_text)
                    self.step_results[task.name].append(Failure(resulting_text))
                    stop_execution = True
                else:
                    result = cloudpickle.loads(running_tasks[task]["queue"].get())
                    self.step_results[task.name].append(result)
                    if not is_successful(result):
                        resulting_type = Failure
                        stop_execution = True

                finished_tasks[task] = {
                    "process": running_tasks[task]["process"],
                    "queue": running_tasks[task]["queue"],
                }

                del running_tasks[task]
                for successor in self.execution_graph.graph.successors(task):
                    waiting_tasks.add(successor)

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
                    waiting_tasks.remove(task)
                    tasks_processed = True

                    # if type - Task -> start and add to running, otherwise just synchronization
                    if isinstance(task, Task):
                        task.previous_steps = deepcopy(self.step_results)
                        serialized_task = cloudpickle.dumps(task)

                        queue: Queue[bytes] = Queue()
                        running_tasks[task] = {
                            "queue": queue,
                            "process": Process(
                                target=self.execute_task, args=(serialized_task, queue)
                            ),
                        }
                        running_tasks[task]["process"].start()
                    else:
                        finished_tasks[task] = {"process": None, "queue": None}
                        self.step_results[str(task)].append(
                            Success("Synchronization task finished.")
                        )
                        for successor in self.execution_graph.graph.successors(task):
                            waiting_tasks.add(successor)

            if not running_tasks and waiting_tasks and not tasks_processed:
                # deadlock?
                self.logger.error("Possible deadlock detected, exiting.")
                self.execution_graph_results = Failure(self.step_results)
                break

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

if __name__ == "__main__":
    Executor().__call__()
