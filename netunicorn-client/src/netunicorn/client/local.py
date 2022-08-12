import asyncio
import copy
from typing import Dict, Tuple, Union

import cloudpickle
import subprocess
from uuid import uuid4
import logging

from returns.result import Result

from .base import BaseClient


from netunicorn.base.minions import Minion, MinionPool
from netunicorn.base.experiment import Experiment, ExperimentStatus, ExperimentExecutionResult
from netunicorn.base.environment_definitions import ShellExecution
from netunicorn.base.pipeline import Pipeline, PipelineResult
from netunicorn.base.utils import NonStablePool as Pool
from netunicorn.executor.executor import PipelineExecutor, PipelineExecutorState


class LocalClient(BaseClient):
    def __init__(self, enforce_environment: bool = False):
        """
        Initializes local client.
        :param enforce_environment: whether to execute
        """
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("LocalClient")
        self._minion_pool = MinionPool([Minion("localhost", {})])
        self.storage = {}
        self.enforce_environment = enforce_environment

    def get_minion_pool(self) -> MinionPool:
        return self._minion_pool

    @staticmethod
    def _execute_pipeline(executor_id: str, pipeline: bytes) -> (str, Result[PipelineResult, PipelineResult]):
        executor = PipelineExecutor(executor_id=executor_id, gateway_ip='localhost')
        executor.pipeline = cloudpickle.loads(pipeline)
        executor.state = PipelineExecutorState.EXECUTING
        asyncio.run(executor.execute())
        return executor_id, pipeline, cloudpickle.dumps(executor.pipeline_results)

    def _install_pipeline(self, pipeline: Pipeline) -> None:
        if not self.enforce_environment:
            self.logger.info(f"Installation of environment for pipeline {pipeline.name}: doing nothing")
        else:
            self.logger.info(f"Flag enforce_environment is set to True, installing prerequisites for the pipeline")
            self.logger.info(f"In the real cluster this installation would be too during deployment.")
            if not isinstance(pipeline.environment_definition, ShellExecution):
                raise ValueError(f"Local client supports only ShellExecution environment definition")

            for command in pipeline.environment_definition.commands:
                self.logger.info(f"Executing command: {command}")
                result = subprocess.run(command, shell=True, capture_output=True)
                self.logger.info(result.stdout.decode())
                self.logger.info(result.stderr.decode())
                if result.returncode != 0:
                    raise RuntimeError(f"Command {command} failed with code {result.returncode}")

            self.logger.info(f"Preparation of environment for pipeline {pipeline.name} finished")

    def prepare_deployment(self, deployment_map: Experiment, deployment_id: str) -> str:
        self.logger.info(f"Starting deployment preparation for {deployment_id}")
        internal_deployment_id = f"depl_{deployment_id}"
        if internal_deployment_id in self.storage:
            self.logger.info("Deployment is already prepared.")
            return internal_deployment_id

        for deployment in deployment_map:
            if not isinstance(deployment.pipeline.environment_definition, ShellExecution):
                raise ValueError(f"Local client supports only ShellExecution environment definition")
            if deployment.minion.name != 'localhost':
                raise ValueError(f"Local client supports only local minion")

        self.storage[internal_deployment_id + "_status"] = ExperimentStatus.PREPARING
        for item in deployment_map:
            item.minion = copy.deepcopy(item.minion)  # bunch of hacks because local execution
            item.minion.additional_properties['executor_id'] = str(uuid4())
            self._install_pipeline(item.pipeline)

        self.storage[internal_deployment_id] = deployment_map
        self.storage[internal_deployment_id + "_status"] = ExperimentStatus.READY
        return deployment_id

    def start_execution(self, deployment_id: str) -> str:
        self.logger.info(f"Starting deployment for {deployment_id}")
        internal_deployment_id = f"depl_{deployment_id}"
        status = self.storage.get(internal_deployment_id + "_status", ExperimentStatus.UNKNOWN)
        if status != ExperimentStatus.READY:
            raise ValueError(f"Deployment is in incorrect status: {status}")

        self.storage[internal_deployment_id + "_status"] = ExperimentStatus.RUNNING
        deployment_map = self.storage[internal_deployment_id]

        process_map = Pool(processes=len(deployment_map), maxtasksperchild=1)

        result = process_map.starmap_async(
            LocalClient._execute_pipeline,
            ((x.minion.additional_properties['executor_id'], cloudpickle.dumps(x.pipeline)) for x in deployment_map)
        )
        self.storage[internal_deployment_id + "_data"] = (
            process_map,
            result,
            {x.minion.additional_properties['executor_id']: x.minion for x in deployment_map}
        )
        self.logger.info(f"Spawned and started {len(deployment_map)} executor(s) for deployment {deployment_id}")
        return deployment_id

    def get_deployment_status(self, deployment_id: str) -> ExperimentStatus:
        internal_deployment_id = f"depl_{deployment_id}"
        if not internal_deployment_id + "_data" in self.storage:
            return self.storage.get(internal_deployment_id + "_status", ExperimentStatus.UNKNOWN)

        if self.storage[internal_deployment_id + "_data"][1].ready():
            self.storage[internal_deployment_id + "_data"][0].close()
            self.storage[internal_deployment_id + "_status"] = ExperimentStatus.FINISHED
            return ExperimentStatus.FINISHED
        return self.storage.get(internal_deployment_id + "_status", ExperimentStatus.UNKNOWN)

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        ExperimentStatus,
        Union[Dict[str, ExperimentExecutionResult], Exception]
    ]:
        internal_deployment_id = f"depl_{deployment_id}"
        if not self.storage[internal_deployment_id + "_data"][1].ready():
            self.logger.info("Pipelines are running. Use 'get_deployment_status' function to check status")
            return ExperimentStatus.RUNNING, {}

        self.storage[internal_deployment_id + "_data"][0].close()
        self.storage[internal_deployment_id + "_status"] = ExperimentStatus.FINISHED
        results = self.storage[internal_deployment_id + "_data"][1].get()
        self.logger.info(f"Collected results for deployment {deployment_id}")

        return ExperimentStatus.FINISHED, {
            result[0]: ExperimentExecutionResult(
                minion=self.storage[internal_deployment_id + "_data"][2][result[0]],
                result=cloudpickle.loads(result[2]),
                pipeline=cloudpickle.loads(result[1])
            ) for result in results
        }
