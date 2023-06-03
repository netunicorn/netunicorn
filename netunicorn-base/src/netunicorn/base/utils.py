"""
Utility functions and classes for netunicorn. Not to be directly used by users.
"""

import dataclasses
from base64 import b64encode
from json import JSONEncoder
from typing import Any, List

from netunicorn.base.environment_definitions import EnvironmentDefinition
from returns.result import Result

SerializedPipelineType = bytes
LogType = List[str]


class UnicornEncoder(JSONEncoder):
    """
    Custom JSON encoder for netunicorn objects.
    """

    def default(self, obj: Any) -> Any:  # pylint: disable=E0202
        """
        Overriden default method for JSONEncoder.

        :param obj: Object to be serialized.
        :return: Serialized object.
        """
        if isinstance(obj, Exception):
            return str(obj.__reduce__())
        if isinstance(obj, set):
            return list(obj)
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if hasattr(obj, "__json__"):
            return obj.__json__()
        if isinstance(obj, bytes):
            return b64encode(obj).decode("utf-8")
        if isinstance(obj, Result):
            # noinspection PyProtectedMember
            return {"result_type": obj.__class__.__name__, "result": obj._inner_value}
        if isinstance(obj, EnvironmentDefinition):
            return {
                "environment_definition_type": obj.__class__.__name__,
                "environment_definition": obj,
            }
        return JSONEncoder.default(self, obj)
