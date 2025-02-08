import asyncio
import base64
from typing import Optional

from yarl import URL

from .handle import CameraHandle
from .pool import CameraPool
from ..asyncio.cancelable_lock import CancelableLock
from ..sp.simplyprint_api import SimplyPrintApi
from ...core.client import Client
from ...core.ws_protocol.messages import WebcamSnapshotDemandData, StreamMsg


class ClientCameraMixin(Client):
    _camera_pool: Optional[CameraPool] = None
    _camera_uri: Optional[URL] = None
    _camera_handle: Optional[CameraHandle] = None
    _stream_lock: CancelableLock
    _stream_setup: asyncio.Event

    def initialize_camera_mixin(
            self,
            camera_pool: Optional[CameraPool] = None,
            **_kwargs
    ):
        self._camera_pool = camera_pool
        self._stream_lock = CancelableLock()
        self._stream_setup = asyncio.Event()

    def set_camera_uri(self, uri: Optional[URL] = None):
        if self._camera_pool is None:
            return

        # If the camera URI is the same, don't recreate the camera.
        if self._camera_uri == uri and self._camera_handle:
            return

        self._camera_uri = uri

        # Clear out previous camera (if URI is different)
        if self._camera_handle:
            self._camera_handle.stop()
            self._camera_handle = None
            self.event_loop.call_soon_threadsafe(self._stream_setup.clear)

        # Create a new camera handle
        if self._camera_uri and self._camera_pool:
            self._camera_handle = self._camera_pool.create(self._camera_uri)
            self.event_loop.call_soon_threadsafe(self._stream_setup.set)

    def __del__(self):
        if self._camera_handle:
            self._camera_handle.stop()

    async def on_stream_on(self):
        await self._stream_setup.wait()

        if not self._camera_handle:
            return

        self._camera_handle.start()

    async def on_stream_off(self):
        if not self._camera_handle:
            return

        self._camera_handle.pause()
        self._stream_lock.cancel()

    async def on_test_webcam(self):
        await self.on_webcam_snapshot(WebcamSnapshotDemandData())

    async def on_webcam_snapshot(self, data: WebcamSnapshotDemandData, retries: int = 3, retry_timeout=5):
        await self._stream_setup.wait()

        # Drop event if no camera is set up.
        if not self._camera_handle:
            return

        # Block until the camera is ready.
        frame = await self._camera_handle.receive_frame()

        # Empty frame or none.
        if not frame:
            if retries > 0:
                self.logger.debug(f"Failed to get frame, retrying in {retry_timeout} seconds")
                await asyncio.sleep(retry_timeout)
                await self.on_webcam_snapshot(data, retries - 1, retry_timeout)
            else:
                self.logger.debug("Failed to get frame, giving up.")

            return

        # Capture snapshot events and send them to the API
        if data.id is not None:
            await SimplyPrintApi.post_snapshot(data.id, frame, endpoint=data.endpoint)
            self.logger.debug(f"Posted snapshot to API with id {data.id}")
            return

        # Mark the webcam as connected if it's not already.
        if not self.printer.webcam_info.connected:
            self.printer.webcam_info.connected = True

        async with self._stream_lock:
            # Prevent racing between receiving frames and sending them.
            await self.printer.intervals.wait_for("webcam")
            b64frame = base64.b64encode(frame).decode("utf-8")
            await self.send(StreamMsg(b64frame))
