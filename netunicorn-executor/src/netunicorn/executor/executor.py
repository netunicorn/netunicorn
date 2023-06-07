import asyncio
import logging
import os
import sys
import time
from asyncio import CancelledError
from base64 import b64decode, b64encode
from collections import defaultdict
from copy import deepcopy
from typing import Any, List, Optional, Tuple, Type, cast

import cloudpickle
import requests as req
import requests.exceptions
from netunicorn.base.pipeline import Pipeline
from netunicorn.base.task import Task, TaskDispatcher
from netunicorn.base.types import PipelineExecutorState, PipelineResult
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from .utils import NonStablePool as Pool
from .utils import safe


class PipelineExecutor:
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

        self.pipeline: Optional[Pipeline] = None
        self.step_results: PipelineResult = defaultdict(list)
        self.pipeline_results: Optional[Result[PipelineResult, PipelineResult]] = None
        self.state = PipelineExecutorState.LOOKING_FOR_PIPELINE

    async def heartbeat(self) -> None:
        while self.state == PipelineExecutorState.EXECUTING:
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
                if self.state == PipelineExecutorState.LOOKING_FOR_PIPELINE:
                    self.request_pipeline()
                elif self.state == PipelineExecutorState.EXECUTING:
                    asyncio.run(self.execute())
                elif self.state == PipelineExecutorState.REPORTING:
                    self.report_results()
                elif self.state == PipelineExecutorState.FINISHED:
                    return
            except Exception as e:
                self.logger.exception(e)
                self.logger.critical("Failed to execute pipeline. Shutting down.")
                self.state = PipelineExecutorState.FINISHED
                break

        # if we break the cycle with an exception, we'll try to report the results
        self.report_results()

    def request_pipeline(self) -> None:
        """
        This method tries to look for pipeline locally to execute, and if not found then asks master for it
        :return: None
        """

        if self.pipeline is not None:
            self.logger.error(
                "request_pipeline is called, but self.pipeline is already set, executing."
            )
            self.state = PipelineExecutorState.EXECUTING
            return

        pipeline_filename = f"unicorn.pipeline"
        if os.path.exists(pipeline_filename):
            with open(pipeline_filename, "rb") as f:
                self.pipeline = cloudpickle.load(f)
                self.logger.info("Pipeline loaded from local file, executing.")
                self.state = PipelineExecutorState.EXECUTING
                return

        try:
            result = req.get(
                f"{self.gateway_endpoint}/api/v1/executor/pipeline?executor_id={self.executor_id}",
                timeout=30,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.info(f"Exception while requesting pipeline: {e} ")
            time.sleep(next(self.backoff_func))
            return

        if result.status_code == 200:
            pipeline = b64decode(result.content)
            self.pipeline = cloudpickle.loads(pipeline)
            self.state = PipelineExecutorState.EXECUTING
            self.logger.info("Successfully received pipeline.")
        else:
            self.logger.info(
                f"Failed to receive pipeline. Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
            )

    @staticmethod
    def execute_task(serialized_task: bytes) -> Tuple[str, bytes]:
        task = cloudpickle.loads(serialized_task)
        result: Result[Any, Any] = safe(task.run)()
        return task.name, cloudpickle.dumps(result)

    def std_redirection(self, *args: Any) -> None:
        _ = args
        sys.stdout = self.print_file
        sys.stderr = self.print_file

    async def execute(self) -> None:
        """
        This method executes the pipeline.
        """

        if self.heartbeat_flag:
            asyncio.create_task(self.heartbeat())

        if not self.pipeline:
            self.logger.error("No pipeline to execute.")
            self.pipeline_results = Failure(self.step_results)
            return

        resulting_type: Type[Result[PipelineResult, PipelineResult]] = Success
        for elements in self.pipeline.tasks:
            if isinstance(elements, Task):
                elements = [elements]
            for task in elements:
                if isinstance(task, TaskDispatcher):
                    self.step_results[task.name].append(
                        Failure("Element is unexpectedly TaskDispatcher")
                    )
                    continue

            element: List[Task] = cast(List[Task], elements)

            # create processes and execute tasks
            with Pool(len(element), initializer=self.std_redirection) as p:
                # attach previous task results to the next step
                for task in element:
                    task.previous_steps = deepcopy(self.step_results)

                serialized_element = [cloudpickle.dumps(task) for task in element]
                execution_results_awaiter = p.map_async(
                    PipelineExecutor.execute_task, serialized_element, chunksize=1
                )

                while not execution_results_awaiter.ready():
                    await asyncio.sleep(1.0)

                execution_results = execution_results_awaiter.get()

            results = tuple(
                (task_name, cloudpickle.loads(result))
                for (task_name, result) in execution_results
            )

            for task_name, result in results:
                self.step_results[task_name].append(result)

            if any(not is_successful(result) for _, result in results):
                resulting_type = Failure
                if self.pipeline.early_stopping:
                    break

        # set flag that pipeline is finished
        self.logger.info("Pipeline finished, start reporting results.")
        self.state = PipelineExecutorState.REPORTING
        self.pipeline_results = resulting_type(self.step_results)

    def report_results(self) -> None:
        """
        This method reports the results to the communicator.
        """
        if isinstance(self.pipeline, Pipeline) and not self.pipeline.report_results:
            self.logger.info("Skipping reporting results due to pipeline setting.")
            self.state = PipelineExecutorState.FINISHED
            return

        with open(self.logfile_name, "rt") as f:
            current_log = f.readlines()

        try:
            results = cloudpickle.dumps([self.pipeline_results, current_log])
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
            self.state = PipelineExecutorState.FINISHED
        else:
            self.logger.warning(
                f"Failed to report results. Status code: {result.status_code}, content: {result.content.decode('utf-8')}"
            )


if __name__ == "__main__":
    PipelineExecutor().__call__()
