import asyncio
from typing import TYPE_CHECKING, Type, List, Optional

from .base import FrameT, BaseCameraProtocol, CameraProtocolPollingMode
from .commands import Request, ConfigureCamera, Response, PollCamera, StartCamera, \
    StopCamera, DeleteCamera, ReceivedFrame
from ..utils.stoppable import StoppableInterface

if TYPE_CHECKING:
    from .pool import CameraPool


class CameraHandle(StoppableInterface):
    """Command proxy for camera instance"""

    pool: 'CameraPool'
    uuid: str
    protocol: Type[BaseCameraProtocol]
    polling_mode: CameraProtocolPollingMode

    _cached_frame: Optional[FrameT] = None
    _waiters: List[asyncio.Future]

    def __init__(self, pool: 'CameraPool', uuid: str, protocol: Type[BaseCameraProtocol]):
        self.pool = pool
        self.uuid = uuid
        self.protocol = protocol
        self.polling_mode = protocol.polling_mode()
        self._waiters = []

    def submit_request(self, req: Request):
        self.pool.submit_request(self.uuid, req)

    def on_response(self, res: Response):
        # Called from one thread only.

        if not isinstance(res, ReceivedFrame):
            return

        self._cached_frame = res.data

        while self._waiters:
            fut = self._waiters.pop(0)

            if fut.done():
                continue

            loop = fut.get_loop()
            loop.call_soon_threadsafe(fut.set_result, res.data)

    async def receive_frame(self, allow_cached=False) -> FrameT:
        if allow_cached and self._cached_frame:
            return self._cached_frame

        self.submit_request(PollCamera())
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._waiters.append(fut)
        return await fut

    def configure(self, config):
        self.submit_request(ConfigureCamera(config))

    def start(self):
        if self.polling_mode == CameraProtocolPollingMode.ON_DEMAND:
            return

        self.submit_request(StartCamera())

    def pause(self):
        if self.polling_mode == CameraProtocolPollingMode.ON_DEMAND:
            return

        self.submit_request(StopCamera())

    # Stoppable methods

    def is_stopped(self) -> bool:
        raise NotImplementedError()

    def stop(self) -> None:
        self.submit_request(DeleteCamera())

    def clear(self) -> None:
        raise NotImplementedError()
