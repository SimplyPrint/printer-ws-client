import functools
import logging
from asyncio.selector_events import _SelectorTransport

f = _SelectorTransport._force_close


@functools.wraps(f)
def _force_close(*args, **kwargs):
    logging.error(f"Force close called from:", stack_info=True)

    return f(*args, **kwargs)


_SelectorTransport._force_close = _force_close
