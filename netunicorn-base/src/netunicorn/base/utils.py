import multiprocessing.pool

from functools import wraps

from returns.result import Failure, Success, Result, Any
from typing import Callable, Union, TypeVar

_ValueType = TypeVar("_ValueType", covariant=True)
_FailureValueType = TypeVar("_FailureValueType", covariant=True)

_FunctionType = Union[
    Callable[..., _ValueType],
    Callable[..., Result[_ValueType, _FailureValueType]]
]

SerializedPipelineType = bytes


def safe(function: _FunctionType) -> Union[
    Callable[..., Result[_ValueType, Exception]],
    Callable[..., Result[_ValueType, _FailureValueType]]
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
        kwargs['context'] = NoDaemonContext()
        super().__init__(*args, **kwargs)
