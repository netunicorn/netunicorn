import dataclasses
import multiprocessing.pool
from base64 import b64encode
from functools import wraps
from json import JSONEncoder
from typing import Callable, List, TypeVar, Union

from netunicorn.base.environment_definitions import EnvironmentDefinition
from returns.result import Any, Failure, Result, Success

_ValueType = TypeVar("_ValueType", covariant=True)
_FailureValueType = TypeVar("_FailureValueType", covariant=True)

_FunctionType = Union[
    Callable[..., _ValueType], Callable[..., Result[_ValueType, _FailureValueType]]
]

SerializedPipelineType = bytes
LogType = List[str]


def safe(
    function: _FunctionType,
) -> Union[
    Callable[..., Result[_ValueType, Exception]],
    Callable[..., Result[_ValueType, _FailureValueType]],
]:
    """
    Decorator that wraps function in try/except block.
    :param function: function to wrap
    :return: wrapped function
    """

    @wraps(function)
    def decorator(*args: Any, **kwargs: Any):
        try:
            result = function(*args, **kwargs)
            if isinstance(result, Result):
                return result
            return Success(result)
        except Exception as exc:
            return Failure(exc.__reduce__())

    return decorator


# If you try to run multiprocessing.Pool inside a multiprocessing.Pool, you'll receive this error:
# AssertionError: daemonic processes are not allowed to have children
# Below is a solution to this problem.
class NoDaemonProcess(multiprocessing.Process):
    @property
    def daemon(self):
        return False

    @daemon.setter
    def daemon(self, value):
        pass


class NoDaemonContext(type(multiprocessing.get_context())):
    Process = NoDaemonProcess


# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NonStablePool(multiprocessing.pool.Pool):
    # noinspection PyArgumentList
    def __init__(self, *args, **kwargs):
        kwargs["context"] = NoDaemonContext()
        super().__init__(*args, **kwargs)


class UnicornEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Exception):
            return obj.__reduce__()
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)
        if hasattr(obj, "__json__"):
            return obj.__json__()
        if isinstance(obj, bytes):
            return b64encode(obj).decode("utf-8")
        if isinstance(obj, Result):
            return {"result_type": obj.__class__.__name__, "result": obj._inner_value}
        if isinstance(obj, EnvironmentDefinition):
            return {
                "environment_definition_type": obj.__class__.__name__,
                "environment_definition": obj,
            }
        return JSONEncoder.default(self, obj)
