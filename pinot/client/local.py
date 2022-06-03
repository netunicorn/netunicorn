import asyncio
import copy
from typing import Dict, Optional, Tuple, Union

import cloudpickle
import subprocess

import logging
from returns.result import Result
from pinot.base.utils import NonStablePool as Pool

from uuid import uuid4
from pinot.base import Pipeline
from pinot.base.minions import Minion, MinionPool
from pinot.base.deployment_map import DeploymentMap, DeploymentStatus, DeploymentExecutionResult
from pinot.base.environment_definitions import ShellExecution
from pinot.base.pipeline import PipelineResult
from pinot.client.base import BaseClient
from pinot.executor.executor import PipelineExecutor, PipelineExecutorState


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

    def compile_pipeline(self, pipeline: Pipeline, environment_id: str) -> str:
        """
        Prepares an environment: does nothing or compiles a pipeline commands if enforce_environment is True.
        """
        environment_id = f"env_{environment_id}"
        if not isinstance(pipeline.environment_definition, ShellExecution):
            raise ValueError(f"Local client supports only ShellExecution environment definition")

        if environment_id in self.storage:
            self.logger.info("Environment preparation already started.")
            return environment_id

        self.storage[environment_id] = pipeline
        return environment_id

    def get_compiled_pipeline(self, environment_id: str) -> Optional[Pipeline]:
        return self.storage[environment_id]

    @staticmethod
    def _execute_pipeline(executor_id: str, pipeline: bytes) -> (str, Result[PipelineResult, PipelineResult]):
        executor = PipelineExecutor(executor_id=executor_id)
        executor.pipeline = cloudpickle.loads(pipeline)
        executor.state = PipelineExecutorState.EXECUTING
        asyncio.run(executor.execute())
        return executor_id, cloudpickle.dumps(executor.pipeline_results)

    def install_pipeline(self, pipeline: Pipeline) -> None:
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

    def deploy_map(self, deployment_map: DeploymentMap, deployment_id: str) -> str:
        self.logger.info(f"Starting deployment for {deployment_id}")
        deployment_id = f"depl_{deployment_id}"
        if deployment_id in self.storage:
            self.logger.info("Deployment already started.")
            return deployment_id

        if any(x.minion.name != 'localhost' for x in deployment_map):
            raise ValueError(f"Local client supports only local minion")

        for item in deployment_map:
            item.minion = copy.deepcopy(item.minion)  # bunch of hacks because local execution
            item.minion.additional_properties['executor_id'] = str(uuid4())
            self.install_pipeline(item.pipeline)

        process_map = Pool(processes=len(deployment_map), maxtasksperchild=1)

        result = process_map.starmap_async(
            LocalClient._execute_pipeline,
            ((x.minion.additional_properties['executor_id'], cloudpickle.dumps(x.pipeline)) for x in deployment_map)
        )
        self.storage[deployment_id] = (
            process_map,
            result,
            {x.minion.additional_properties['executor_id']: x.minion for x in deployment_map}
        )
        self.logger.info(f"Spawned and started {len(deployment_map)} executor(s) for deployment {deployment_id}")
        return deployment_id

    def get_deployment_status(self, deployment_id: str) -> DeploymentStatus:
        if self.storage[deployment_id][1].ready():
            self.storage[deployment_id][0].close()
            return DeploymentStatus.FINISHED
        return DeploymentStatus.RUNNING

    def get_deployment_result(self, deployment_id: str) -> Tuple[
        DeploymentStatus,
        Union[Dict[str, DeploymentExecutionResult], Exception]
    ]:
        if not self.storage[deployment_id][1].ready():
            self.logger.info("Pipelines are running. Use 'get_deployment_status' function to check status")
            return DeploymentStatus.RUNNING, {}

        self.storage[deployment_id][0].close()
        results = self.storage[deployment_id][1].get()
        self.logger.info(f"Collected results for deployment {deployment_id}")

        return DeploymentStatus.FINISHED, {
            result[0]: DeploymentExecutionResult(
                minion=self.storage[deployment_id][2][result[0]],
                result=cloudpickle.loads(result[1])
            ) for result in results
        }
