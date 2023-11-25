import multiprocessing.pool
import traceback
from functools import wraps
from typing import Any, Callable, TypeVar, Union

from returns.result import Failure, Result, Success

_ValueType = TypeVar("_ValueType", covariant=True)
_FailureValueType = TypeVar("_FailureValueType", covariant=True)


_FunctionType = Union[
    Callable[..., _ValueType], Callable[..., Result[_ValueType, _FailureValueType]]
]


def safe(
    function: _FunctionType[Any, Any],
) -> Union[
    Callable[..., Result[_ValueType, Exception]],
    Callable[..., Result[_ValueType, _FailureValueType]],
]:
    """
    Decorator that wraps function in try/except block and always returns Result object.

    :param function: function to wrap
    :return: wrapped function that always returns Result object
    """

    @wraps(function)
    def decorator(*args: Any, **kwargs: Any) -> Result[Any, Any]:
        try:
            result = function(*args, **kwargs)
            if isinstance(result, Result):
                return result
            return Success(result)
        except Exception:
            traceback.print_exc()
            return Failure(traceback.format_exc())

    return decorator


class NoDaemonProcess(multiprocessing.Process):
    """
    | If you try to run multiprocessing.Pool inside a multiprocessing.Pool, you'll receive this error:
    | AssertionError: daemonic processes are not allowed to have children
    | This class is a solution to this problem.
    """

    @property
    def daemon(self) -> bool:
        """
        Returns if the process is daemon.
        """
        return False

    @daemon.setter
    def daemon(self, value: Any) -> None:
        """
        Sets the daemon value for the process.
        """
        pass


class NoDaemonContext(type(multiprocessing.get_context())):  # type: ignore
    """
    Context for multiprocessing.Pool that uses NoDaemonProcess instead of multiprocessing.Process.
    """

    Process = NoDaemonProcess
    """
    Process class to use.
    """


class NonStablePool(multiprocessing.pool.Pool):
    """
    We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool because
        the latter is only a wrapper function, not a proper class.
    """

    # noinspection PyArgumentList
    def __init__(self, *args: Any, **kwargs: Any):
        kwargs["context"] = NoDaemonContext()
        super().__init__(*args, **kwargs)
