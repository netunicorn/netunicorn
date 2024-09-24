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
