import dataclasses
import multiprocessing.pool
from base64 import b64encode
from functools import wraps
from json import JSONEncoder
from typing import Any, Callable, List, TypeVar, Union

from netunicorn.base.environment_definitions import EnvironmentDefinition
from returns.result import Failure, Result, Success

_ValueType = TypeVar("_ValueType", covariant=True)
_FailureValueType = TypeVar("_FailureValueType", covariant=True)

_FunctionType = Union[
    Callable[..., _ValueType], Callable[..., Result[_ValueType, _FailureValueType]]
]

SerializedPipelineType = bytes
LogType = List[str]


def safe(
    function: _FunctionType,  # type: ignore
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
    def decorator(*args: Any, **kwargs: Any) -> Result[Any, Any]:
        try:
            result = function(*args, **kwargs)
            if result is None:
                # Well, ok. The problem is that if we create Success(None) object,
                # cloudpickle serialization somewhere breaks and we receive this error:
                # AttributeError: 'Success' object has no attribute '_inner_value'
                # So, for now - we return 0 instead of None until we find and fix/report the bug.
                result = 0
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
    def daemon(self) -> bool:
        return False

    @daemon.setter
    def daemon(self, value: Any) -> None:
        pass


class NoDaemonContext(type(multiprocessing.get_context())):  # type: ignore
    Process = NoDaemonProcess


# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NonStablePool(multiprocessing.pool.Pool):
    # noinspection PyArgumentList
    def __init__(self, *args: Any, **kwargs: Any):
        kwargs["context"] = NoDaemonContext()
        super().__init__(*args, **kwargs)


class UnicornEncoder(JSONEncoder):
    def default(self, obj: Any) -> Any:  # pylint: disable=E0202
        if isinstance(obj, Exception):
            return str(obj.__reduce__())
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
