import functools
import logging
from asyncio.selector_events import _SelectorTransport

from .traceability import traceable

f = _SelectorTransport._force_close


@functools.wraps(f)
@traceable(with_args=True, with_stack=True, record_count=20)
def _force_close(*args, **kwargs):
    logging.error(f"Force close called from:", stack_info=True)

    return f(*args, **kwargs)


_SelectorTransport._force_close = _force_close
