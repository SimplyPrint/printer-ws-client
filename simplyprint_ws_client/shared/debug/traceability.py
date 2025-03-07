import contextlib
import contextvars
import dataclasses
import sys
import time
import traceback
from collections import deque
from functools import wraps
from typing import Optional

from ..utils.exception_as_value import exception_as_value

_traceability_enabled = contextvars.ContextVar("_traceability_enabled", default=False)


@contextlib.contextmanager
def enable_traceable(enabled=True):
    token = _traceability_enabled.set(enabled)

    try:
        yield
    finally:
        _traceability_enabled.reset(token)


def traceable_location_from_func(func, *args, **kwargs):
    # If the function is a method, we store it on the instance
    # therefore we suffix the key with the function name.
    if hasattr(func, "__self__"):
        return func.__self__, f"__traceability__{func.__name__}", True

    # For property functions if the first argument is a class
    # and that class has the property, we store it on the class
    if args and hasattr(args[0], '__class__') and hasattr(args[0].__class__, func.__name__):
        return args[0], f"__traceability__{func.__name__}", True

    # Otherwise, we store it on the function itself
    return func, "__traceability__", False


# Collects traceability information for a function
# Into an object that can be used to trace the function call
def traceable(*args, record_calls=False, with_stack=False, with_args=False, with_retval=False, record_count=10,
              **kwargs):
    """
    :param record_calls: Whether to record the number of calls to the function
    :param with_stack: Whether to record the stack of the function
    :param with_args: Whether to record the arguments of the function
    :param with_retval: Whether to record the return value of the function
    :param record_count: The number of records to keep
    """

    should_record_calls = record_calls or with_stack or with_args or with_retval

    def decorator(func):
        if not callable(func):
            raise ValueError("traceable decorator must be used on a callable")

        # Required as property is mirrored by @wraps so we can reference "func" in this context
        setattr(func, "__traceability__", Traceability(
            last_called=None,
            call_record=deque(maxlen=record_count) if should_record_calls else None
        ))

        @wraps(func)
        def wrapper(*fargs, **fkwargs):
            # If traceability is disabled, we just call the function
            # Getting a smaller runtime overhead.
            if not _traceability_enabled.get():
                return func(*fargs, **fkwargs)

            obj, trace_key, remove_first_arg = traceable_location_from_func(func, *fargs, **fkwargs)

            if hasattr(obj, trace_key):
                traceability = getattr(obj, trace_key)
            else:
                traceability = Traceability(
                    last_called=None,
                    call_record=deque(maxlen=10) if should_record_calls else None
                )

                setattr(obj, trace_key, traceability)

            traceability.last_called = time.time()

            retval = None

            try:
                retval = func(*fargs, **fkwargs)
                return retval
            finally:
                if should_record_calls:
                    record = TraceabilityRecord(
                        called_at=traceability.last_called,
                        args=(fargs[1:] if remove_first_arg else fargs) if with_args else None,
                        kwargs=fkwargs if with_args else None,
                        retval=retval if with_retval else None,
                        stack=None,
                    )

                    if with_stack:
                        record.stack = traceback.extract_stack()

                    traceability.call_record.append(record)

        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])

    return decorator


@exception_as_value(return_default=True)
def from_func(func):
    obj, key, _ = traceable_location_from_func(func)

    if not hasattr(obj, key):
        raise ValueError("Function does not have traceability information")

    traceability = getattr(obj, key)

    if not isinstance(traceability, Traceability):
        raise ValueError("Traceability information is not of the correct type")

    return traceability


@exception_as_value(return_default=True)
def from_property(prop: property):
    return from_func(prop.fget), from_func(prop.fset)


def from_class_instance(cls):
    # Find all properties starting with __traceability__
    traces = {
        name[len("__traceability__"):]: value for name, value in cls.__dict__.items()
        if name.startswith("__traceability__")
    }

    # Return name: Traceability
    return {
        name: value for name, value in traces.items()
        if isinstance(value, Traceability)
    }


def from_class_static(cls):
    # Find all callables that have the property __traceability__
    traces = {
        name: value for name, value in cls.__dict__.items()
        if hasattr(value, "__traceability__")
    }

    return {
        name: from_func(value) for name, value in traces.items()
    }


@exception_as_value(return_default=True)
def from_class(cls):
    if isinstance(cls, type):
        return from_class_static(cls)

    return from_class_instance(cls)


py310 = sys.version_info.minor >= 10 or sys.version_info.major > 3
py38 = sys.version_info.minor <= 8 or sys.version_info.major <= 3
TRecords = deque if py38 else deque["TraceabilityRecord"]


@dataclasses.dataclass(**({"slots": True} if py310 else {}))
class TraceabilityRecord:
    called_at: float
    args: Optional[tuple] = None
    kwargs: Optional[dict] = None
    retval: Optional[object] = None
    stack: Optional[traceback.StackSummary] = None


@dataclasses.dataclass(**({"slots": True} if py310 else {}))
class Traceability:
    last_called: Optional[float]
    call_record: Optional[TRecords] = None

    def stats(self):
        return {
            "last_called":  self.last_called,
            "delta_called": time.time() - self.last_called
        }

    def get_call_record(self):
        return list(self.call_record) if self.call_record else []


__all__ = [
    "traceable",
    "enable_traceable",
    "from_func",
    "from_property",
    "from_class",
    "Traceability",
    "TraceabilityRecord"
]
