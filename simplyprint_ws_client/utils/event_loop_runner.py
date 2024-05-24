import asyncio
import contextlib
import contextvars
from typing import List, Callable

try:
    """ Prefer faster event loop implementation. """
    from uvloop import run as async_run
except ImportError:
    from asyncio import run as async_run

_asyncio_debug_enabled = contextvars.ContextVar("_debug_enabled", default=False)


@contextlib.contextmanager
def enable_asyncio_debug():
    token = _asyncio_debug_enabled.set(True)
    try:
        yield
    finally:
        _asyncio_debug_enabled.reset(token)


class EventLoopRunner:
    """ Wrapper around uvloop/asyncio implementations for running the main event loop. """
    debug = False
    context_stack: List[Callable[[], contextlib.AbstractContextManager]]

    def __init__(self, debug=False, context_stack=None):
        self.debug = debug
        self.context_stack = [] if context_stack is None else context_stack

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def run(self, *args, **kwargs) -> None:
        try:
            with contextlib.ExitStack() as stack:
                for context_func in self.context_stack:
                    stack.enter_context(context_func())

                return async_run(*args, debug=_asyncio_debug_enabled.get() or self.debug, **kwargs)
        except asyncio.CancelledError:
            pass
