import json
import platform
import unittest
from base64 import b64encode

from netunicorn.base.deployment import Deployment
from netunicorn.base.experiment import DeploymentExecutionResult, Experiment
from netunicorn.base.minions import Minion, MinionPool
from netunicorn.base.pipeline import Pipeline
from netunicorn.base.task import Task
from netunicorn.base.utils import UnicornEncoder

cloudpickle_version = None
try:
    import cloudpickle

    cloudpickle_version = cloudpickle.__version__
except ImportError:
    pass


class TestAllJSONSerialization(unittest.TestCase):
    def test_minions(self):
        minion_pool = MinionPool(
            [
                Minion("minion1", {"prop1": "value1", "prop2": "value2"}),
                Minion("minion2", {"prop1": "value1", "prop2": "value2"}),
            ]
        )
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
                "properties": {"prop1": "value1", "prop2": "value2"},
                "additional_properties": {},
                "architecture": "unknown",
            },
            "prepared": False,
            "executor_id": "",
            "error": "test",
            "pipeline": b64encode(deployment.pipeline).decode("utf-8"),
            "environment_definition": {
                "commands": [],
                "image": None,
                "build_context": {
                    "python_version": platform.python_version(),
                    "cloudpickle_version": cloudpickle_version,
                },
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
        self.assertEqual(
            deployment.environment_definition,
            deserialized_deployment.environment_definition,
        )

    def test_experiment(self):
        self.maxDiff = None
        minion = Minion("minion1", {"prop1": "value1", "prop2": "value2"})
        pipeline = Pipeline().then(Task())
        experiment = Experiment().append(minion, pipeline)
        json_experiment = UnicornEncoder().encode(experiment)
        deserialized_experiment = Experiment.from_json(json.loads(json_experiment))
        self.assertEqual(
            experiment.keep_alive_timeout_minutes,
            deserialized_experiment.keep_alive_timeout_minutes,
        )
        self.assertEqual(
            len(experiment.deployment_map), len(deserialized_experiment.deployment_map)
        )

    def test_pipeline_execution_result(self):
        self.maxDiff = None
        minion = Minion("minion1", {})
        pipeline = b"dsa"
        results = b"asd"

        execution_result = DeploymentExecutionResult(minion, pipeline, results)
        json_execution_result = UnicornEncoder().encode(execution_result)
        deserialized_execution_result = DeploymentExecutionResult.from_json(
            json.loads(json_execution_result)
        )

        self.assertEqual(execution_result.minion, deserialized_execution_result.minion)
