import functools
from typing import Type, Union, Tuple


def exception_as_value(*args, return_default=False, default=None, **kwargs):
    """ Internal decorator to return an exception as a value

    Only used to minimize runtime overhead.
    """

    def decorator(func):
        if not callable(func):
            raise ValueError("exception_as_value decorator must be used on a callable")

        @functools.wraps(func)
        def wrapper(*fargs, **fkwargs):
            try:
                return func(*fargs, **fkwargs)
            except Exception as e:
                return e if not return_default else default

        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])

    return decorator


def exception_as_another(exc: Type[BaseException], wrap=True,
                         catch: Union[Type[BaseException], Tuple[Type[BaseException]]] = BaseException):
    """Replace uncaught exception with another type of exception"""

    def decorator(func):
        if not callable(func):
            raise ValueError("uncaught_exception_as_another decorator must be used on a callable")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except catch as e:

                if wrap:
                    e = exc(e)
                else:
                    e = exc()

                raise e

        return wrapper

    return decorator
