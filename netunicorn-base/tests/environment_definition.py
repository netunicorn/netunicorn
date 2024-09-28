import json
import unittest

from netunicorn.base.environment_definitions import RuntimeContext
from netunicorn.base.utils import UnicornEncoder


class TestEnvironmentDefinitions(unittest.TestCase):
    def test_runtime_context_serialization(self):
        ports_mapping = {8080: 8080}
        environment_variables = {"ENV_VAR": "value"}
        network = "randomvalue"
        additional_arguments = ["--some-argument"]
        runtime_context = RuntimeContext(
            ports_mapping=ports_mapping,
            environment_variables=environment_variables,
            additional_arguments=additional_arguments,
            network=network,
        )
        json_runtime_context = UnicornEncoder().encode(runtime_context)
        deserialized_runtime_context = RuntimeContext.from_json(
            json.loads(json_runtime_context)
        )

        self.assertEqual(runtime_context, deserialized_runtime_context)
