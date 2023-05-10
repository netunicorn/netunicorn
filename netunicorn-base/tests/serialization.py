import json
import platform
import unittest
from base64 import b64encode

from netunicorn.base.deployment import Deployment
from netunicorn.base.experiment import DeploymentExecutionResult, Experiment
from netunicorn.base.nodes import CountableNodePool, Node, Nodes
from netunicorn.base.pipeline import Pipeline
from netunicorn.base.task import Task
from netunicorn.base.utils import UnicornEncoder

cloudpickle_version = None
try:
    import cloudpickle

    cloudpickle_version = cloudpickle.__version__
except ImportError:
    pass


class DummyTask(Task):
    def run(self):
        return 0


class TestAllJSONSerialization(unittest.TestCase):
    def test_nodes(self):
        node_pool = CountableNodePool(
            [
                Node("node1", {"prop1": "value1", "prop2": "value2"}),
                Node("node2", {"prop1": "value1", "prop2": "value2"}),
            ]
        )
        json_node_pool = UnicornEncoder().encode(node_pool)
        deserialized_node_pool = Nodes.dispatch_and_deserialize(
            json.loads(json_node_pool)
        )
        for _ in range(len(node_pool)):
            left_element = node_pool.take(1)[0]
            right_element = deserialized_node_pool.take(1)[0]
            self.assertEqual(left_element, right_element)

    def test_deployment(self):
        self.maxDiff = None
        node = Node("node1", {"prop1": "value1", "prop2": "value2"})
        pipeline = Pipeline().then(DummyTask())
        deployment = Deployment(node, pipeline)
        deployment.error = Exception("test")
        json_deployment = UnicornEncoder().encode(deployment)

        encoded_object = {
            "node": {
                "name": "node1",
                "properties": {"prop1": "value1", "prop2": "value2"},
                "additional_properties": {},
                "architecture": "unknown",
            },
            "prepared": False,
            "executor_id": "",
            "error": "test",
            "pipeline": b64encode(deployment.pipeline).decode("utf-8"),
            "keep_alive_timeout_minutes": 10,
            "cleanup": True,
            "environment_definition": {
                "commands": [],
                "image": None,
                "build_context": {
                    "python_version": platform.python_version(),
                    "cloudpickle_version": cloudpickle_version,
                },
                "runtime_context": {
                    "additional_arguments": [],
                    "environment_variables": {},
                    "ports_mapping": {},
                },
            },
            "environment_definition_type": "DockerImage",
        }
        self.assertEqual(json.loads(json_deployment), encoded_object)

        deserialized_deployment = Deployment.from_json(json.loads(json_deployment))
        self.assertEqual(deployment.node, deserialized_deployment.node)
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
        node = Node("node1", {"prop1": "value1", "prop2": "value2"})
        pipeline = Pipeline().then(DummyTask())
        experiment = Experiment().append(node, pipeline)
        json_experiment = UnicornEncoder().encode(experiment)
        deserialized_experiment = Experiment.from_json(json.loads(json_experiment))
        self.assertEqual(
            len(experiment.deployment_map), len(deserialized_experiment.deployment_map)
        )

    def test_pipeline_execution_result(self):
        self.maxDiff = None
        node = Node("node1", {})
        pipeline = b"dsa"
        results = b"asd"

        execution_result = DeploymentExecutionResult(node, pipeline, results)
        json_execution_result = UnicornEncoder().encode(execution_result)
        deserialized_execution_result = DeploymentExecutionResult.from_json(
            json.loads(json_execution_result)
        )

        self.assertEqual(execution_result.node, deserialized_execution_result.node)
