import asyncio
import time
from typing import TYPE_CHECKING, List, Tuple, Optional

from .base import FrameT
from .commands import Response, PollCamera, StartCamera, \
    StopCamera, DeleteCamera, ReceivedFrame
from ..utils.stoppable import StoppableInterface

if TYPE_CHECKING:
    from .pool import CameraPool


class CameraHandle(StoppableInterface):
    pool: 'CameraPool'
    id: int

    _waiters: List[asyncio.Future]
    _frame_time_window: List[float]
    _last_poll_time: float
    _cached_frame: Optional[Tuple[float, FrameT]] = None

    def __init__(self, pool: 'CameraPool', camera_id: int):
        self.pool = pool
        self.id = camera_id
        self._frame_time_window = []
        self._waiters = []

    def on_response(self, res: Response):
        # Called from one thread only.
        if not isinstance(res, ReceivedFrame):
            return

        # Keep track of last 10 frame times
        self._frame_time_window.append(res.time)

        if len(self._frame_time_window) > 10:
            self._frame_time_window.pop(0)

        self._cached_frame = (res.time, res.data)

        while self._waiters:
            fut = self._waiters.pop(0)

            if fut.done():
                continue

            loop = fut.get_loop()
            loop.call_soon_threadsafe(fut.set_result, res.data)

    async def receive_frame(self, allow_cached=False) -> FrameT:
        # Old frame
        if allow_cached and self._cached_frame is not None:
            return self._cached_frame[1]

        # New frame
        self.pool.submit_request(PollCamera(self.id))
        self._last_poll_time = time.time()
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._waiters.append(fut)
        return await fut

    def start(self):
        self.pool.submit_request(StartCamera(self.id))

    def pause(self):
        self.pool.submit_request(StopCamera(self.id))

    # Stoppable methods

    def is_stopped(self) -> bool:
        raise NotImplementedError()

    def stop(self) -> None:
        self.pool.submit_request(DeleteCamera(self.id))

    def clear(self) -> None:
        raise NotImplementedError()
