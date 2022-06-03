import os
import asyncio
import logging
import cloudpickle
import requests as req
from pinot.base.utils import NonStablePool as Pool
import requests.exceptions

from enum import Enum

from base64 import b64encode, b64decode
from copy import deepcopy

from typing import List, Collection, Optional
from returns.result import Result, Success, Failure
from returns.pipeline import is_successful

from pinot.base.task import Task
from pinot.base.pipeline import Pipeline, PipelineResult, PipelineElementResult


class PipelineExecutorState(Enum):
    WAITING_FOR_PIPELINE = 0
    EXECUTING = 1
    REPORTING = 2
    FINISHED = 3


class PipelineExecutor:
    def __init__(self, executor_id: str = None, gateway_ip: str = None, gateway_port: int = None):
        # load up our own ID and the local communicator info
        self.executor_id: str = executor_id or os.environ.get("PINOT_EXECUTOR_ID") or "Unknown"
        self.dir_ip: str = gateway_ip or os.environ.get("PINOT_GATEWAY_IP") or "127.0.0.1"
        self.dir_port: int = int(gateway_port or os.environ.get("PINOT_GATEWAY_PORT") or "26512")

        logging.basicConfig()
        self.logger = self.create_logger(self.executor_id)
        self.logger.info(f"Parsed configuration: Gateway located on {self.dir_ip}:{self.dir_port}")

        self.pipeline: Optional[Pipeline] = None
        self.step_results: List[PipelineElementResult] = []
        self.pipeline_results: Optional[Result[PipelineResult, PipelineResult]] = None
        self.state = PipelineExecutorState.WAITING_FOR_PIPELINE

    @staticmethod
    def create_logger(executor_id: str) -> logging.Logger:
        logger = logging.getLogger(f"executor_{executor_id}")
        logger.addHandler(logging.FileHandler(f'executor_{executor_id}.log'))
        logger.setLevel(logging.INFO)
        return logger

    def __call__(self) -> None:
        """
        This method is the main loop of the executor.
        :return: None
        """
        # TODO: add keepalive in the background that will send current state
        while True:
            try:
                if self.state == PipelineExecutorState.WAITING_FOR_PIPELINE:
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
                return

    def request_pipeline(self) -> None:
        """
        This method requests the pipeline from the communicator and set it.
        :return: None
        """
        try:
            # TODO: https
            result = req.get(
                f"http://{self.dir_ip}:{self.dir_port}/api/v1/executor/pipeline?executor_id={self.executor_id}",
                timeout=30
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.info(f"Exception while requesting pipeline: {e} ")
            return

        if result.status_code == 200:
            result = cloudpickle.loads(b64decode(result.content))
            self.pipeline = cloudpickle.loads(result)
            self.state = PipelineExecutorState.EXECUTING
            self.logger.info("Successfully received pipeline.")
        else:
            self.logger.info(
                f"Failed to receive pipeline. Status code: {result.status_code}, content: {result.content}")

    @staticmethod
    def execute_task(task: bytes) -> None:
        task = cloudpickle.loads(task)
        result = task.run()
        return cloudpickle.dumps(result)

    async def execute(self) -> None:
        """
        This method executes the pipeline.
        """

        if not self.pipeline:
            self.logger.info("No pipeline to execute.")
            self.pipeline_results = Failure(tuple(self.step_results))
            return

        resulting_type = Success
        for element in self.pipeline.tasks:

            if isinstance(element, Task):
                element = [element]

            # create processes and execute tasks
            with Pool(len(element)) as p:
                # attach previous task results to the next step
                for task in element:
                    task.previous_results = deepcopy(self.step_results)

                element = [cloudpickle.dumps(task) for task in element]
                results = p.map_async(PipelineExecutor.execute_task, element, chunksize=1)

                while not results.ready():
                    await asyncio.sleep(1.0)

                results = results.get()

            results = tuple(cloudpickle.loads(result) for result in results)
            results = results[0] if len(results) == 1 else results
            self.step_results.append(results)

            if (
                    (isinstance(results, Result) and not is_successful(results)) or
                    (isinstance(results, Collection) and any(not is_successful(result) for result in results))
            ):
                resulting_type = Failure
                if self.pipeline.early_stopping:
                    break

        # set flag that pipeline is finished
        self.state = PipelineExecutorState.REPORTING
        self.pipeline_results = resulting_type(tuple(self.step_results))

    def report_results(self) -> None:
        """
        This method reports the results to the communicator.
        """
        results = self.pipeline_results
        results = cloudpickle.dumps(results)
        results = b64encode(results)
        try:
            # TODO: https
            result = req.post(
                f"http://{self.dir_ip}:{self.dir_port}/api/v1/executor/result",
                json={"executor_id": self.executor_id, "results": results},
                timeout=30
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            self.logger.info(f"Exception while reporting results: {e} ")
            return

        if result.status_code == 200:
            self.state = PipelineExecutorState.FINISHED
        else:
            self.logger.warning(
                f"Failed to report results. Status code: {result.status_code}, content: {result.content}")


if __name__ == '__main__':
    PipelineExecutor().__call__()

# TODO: add event system
#  short idea: task should somehow be able to send and receive events,
#  probably pass to run() some object that would allow to do it
