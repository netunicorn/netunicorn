import platform
import unittest
import json
from base64 import b64encode
from returns.result import Success, Failure

from netunicorn.base.utils import UnicornEncoder
from netunicorn.base.minions import Minion, MinionPool
from netunicorn.base.deployment import Deployment
from netunicorn.base.experiment import Experiment, ExperimentExecutionResult
from netunicorn.base.pipeline import Pipeline
from netunicorn.base.task import Task


class TestAllJSONSerialization(unittest.TestCase):

    def test_minions(self):
        minion_pool = MinionPool([
            Minion("minion1", {"prop1": "value1", "prop2": "value2"}),
            Minion("minion2", {"prop1": "value1", "prop2": "value2"}),
        ])
        json_minion_pool = UnicornEncoder().encode(minion_pool)
        deserialized_minion_pool = MinionPool.from_json(json.loads(json_minion_pool))
        for x in range(len(minion_pool)):
            self.assertEqual(minion_pool[x], deserialized_minion_pool[x])

    def test_deployment(self):
        self.maxDiff = None
        minion = Minion("minion1", {"prop1": "value1", "prop2": "value2"})
        pipeline = Pipeline().then(Task())
        deployment = Deployment(minion, pipeline)
        deployment.error = Exception("test")
        json_deployment = UnicornEncoder().encode(deployment)

        encoded_object = {
                    "minion": {
                        "name": "minion1",
                        "properties": {
                            "prop1": "value1",
                            "prop2": "value2"
                        },
                        "additional_properties": {},
                        "architecture": "unknown",
                    },
                    "prepared": False,
                    "executor_id": "Unknown",
                    "error": "test",
                    "pipeline": b64encode(deployment.pipeline).decode("utf-8"),
                    "environment_definition": {
                        "commands": [],
                        "image": None,
                        "python_version": platform.python_version(),
                    },
                    "environment_definition_type": "DockerImage",
                }
        self.assertEqual(json.loads(json_deployment), encoded_object)

        deserialized_deployment = Deployment.from_json(json.loads(json_deployment))
        self.assertEqual(deployment.minion, deserialized_deployment.minion)
        self.assertEqual(deployment.prepared, deserialized_deployment.prepared)
        self.assertEqual(deployment.executor_id, deserialized_deployment.executor_id)
        self.assertEqual(str(deployment.error), str(deserialized_deployment.error))
        self.assertEqual(deployment.pipeline, deserialized_deployment.pipeline)
        self.assertEqual(deployment.environment_definition, deserialized_deployment.environment_definition)

    def test_experiment(self):
        self.maxDiff = None
        minion = Minion("minion1", {"prop1": "value1", "prop2": "value2"})
        pipeline = Pipeline().then(Task())
        experiment = Experiment().append(minion, pipeline)
        json_experiment = UnicornEncoder().encode(experiment)
        deserialized_experiment = Experiment.from_json(json.loads(json_experiment))
        self.assertEqual(experiment.keep_alive_timeout_minutes, deserialized_experiment.keep_alive_timeout_minutes)
        self.assertEqual(len(experiment.deployment_map), len(deserialized_experiment.deployment_map))

    def test_pipeline_execution_result(self):
        self.maxDiff = None
        minion = Minion("minion1", {})
        pipeline = b'dsa'
        results = b'asd'

        for x in results:
            execution_result = ExperimentExecutionResult(minion, pipeline, results)
            json_execution_result = UnicornEncoder().encode(execution_result)
            deserialized_execution_result = ExperimentExecutionResult.from_json(json.loads(json_execution_result))

            self.assertEqual(execution_result.minion, deserialized_execution_result.minion)
