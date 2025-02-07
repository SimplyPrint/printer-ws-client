import asyncio
import base64
from typing import Type, Optional

from .base import BaseCameraProtocol, TCameraConfig, TCameraState
from .handle import CameraHandle
from .pool import CameraPool
from ..sp.simplyprint_api import SimplyPrintApi
from ...core.client import Client
from ...core.ws_protocol.messages import WebcamSnapshotDemandData, StreamMsg


class ClientCameraMixin(Client):
    _camera_handle: Optional[CameraHandle] = None
    _stream_lock: asyncio.Lock

    def initialize_camera_handle(  # noqa
            self,
            protocol: Type[BaseCameraProtocol[TCameraConfig, TCameraState]],
            config: TCameraConfig,
            camera_pool: Optional[CameraPool] = None,
            **kwargs,
    ):
        if camera_pool is not None:
            self._camera_handle = camera_pool.create(protocol, config)
            self.logger.debug(f"Created camera handle for {protocol.__name__}")

        self._stream_lock = asyncio.Lock()

    def __del__(self):
        if self._camera_handle:
            self._camera_handle.stop()

    async def on_stream_on(self):
        if not self._camera_handle:
            return

        self._camera_handle.start()

    async def on_stream_off(self):
        if not self._camera_handle:
            return

        self._camera_handle.pause()

    async def on_test_webcam(self):
        await self.on_webcam_snapshot(WebcamSnapshotDemandData())

    async def on_webcam_snapshot(self, data: WebcamSnapshotDemandData):
        if not self._camera_handle:
            return

        is_snapshot_request = data.id is not None

        # This blocks asynchronously until the camera is ready.
        frame = await self._camera_handle.receive_frame(allow_cached=is_snapshot_request)

        # TODO: Retry logic.
        if not frame:
            print("No frame!!!!")
            return

        # Capture snapshot events and send them to the API
        if is_snapshot_request:
            # Post snapshot to API
            await SimplyPrintApi.post_snapshot(data.id, frame, endpoint=data.endpoint)
            self.logger.debug(f"Posted snapshot to API with id {data.id}")
            return

        self.printer.webcam_info.connected = True

        async with self._stream_lock:
            await self.printer.intervals.wait_for("webcam")
            b64frame = base64.b64encode(frame).decode("utf-8")
            await self.send(StreamMsg(b64frame))
