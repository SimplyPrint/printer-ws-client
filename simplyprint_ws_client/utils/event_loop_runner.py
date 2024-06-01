import asyncio
import contextlib
import contextvars
from enum import Enum
from typing import List, Callable, Optional

try:
    import uvloop
except ImportError:
    uvloop = None


class EventLoopBackend(Enum):
    AUTO = "auto"
    UVLOOP = "uvloop"
    ASYNCIO = "asyncio"

    @property
    def runner(self) -> Callable:
        if self is EventLoopBackend.AUTO:
            # Prefer UVLoop if available
            return uvloop.run if uvloop is not None else asyncio.run

        if self is EventLoopBackend.UVLOOP:
            assert uvloop is not None, "uvloop is not installed"
            return uvloop.run

        return asyncio.run


_loop_debug_enabled = contextvars.ContextVar("_loop_debug_enabled", default=False)
_loop_backend = contextvars.ContextVar("_loop_backend", default=EventLoopBackend.AUTO)


@contextlib.contextmanager
def enable_asyncio_debug():
    token = _loop_debug_enabled.set(True)
    try:
        yield
    finally:
        _loop_debug_enabled.reset(token)


class EventLoopRunner:
    """ Wrapper around uvloop/asyncio implementations for running the main event loop. """
    debug = False
    context_stack: List[Callable[[], contextlib.AbstractContextManager]]
    backend: Optional[EventLoopBackend] = None

    def __init__(self, debug=False, context_stack=None, backend=None):
        self.debug = debug
        self.context_stack = [] if context_stack is None else context_stack
        self.backend = backend

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def run(self, *args, **kwargs) -> None:
        try:
            with contextlib.ExitStack() as stack:
                for context_func in self.context_stack:
                    stack.enter_context(context_func())

                debug = self.debug or _loop_debug_enabled.get()
                backend = self.backend or _loop_backend.get()

                return backend.runner(*args, debug=debug, **kwargs)
        except asyncio.CancelledError:
            pass
