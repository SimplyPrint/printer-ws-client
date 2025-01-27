"""Simple async controller to intermittently re-send `file_progress` to refresh the 30-second client side timeout."""

__all__ = ['FakeFileProgress']

from typing import Optional

from simplyprint_ws_client.core.client import Client
from simplyprint_ws_client.core.state import FileProgressStateEnum
from simplyprint_ws_client.shared.asyncio.continuous_task import ContinuousTask
from simplyprint_ws_client.shared.utils.backoff import Backoff, ConstantBackoff
from simplyprint_ws_client.shared.utils.stoppable import AsyncStoppable


class FakeFileProgress(AsyncStoppable):
    client: Client
    backoff: Backoff
    fake_progress_task: ContinuousTask

    def __init__(self, client: Client, backoff: Optional[Backoff] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.backoff = backoff or ConstantBackoff(5)
        self.fake_progress_task = ContinuousTask(self.fake_progress)

    @property
    def is_downloading(self):
        return self.client.printer.file_progress.state == FileProgressStateEnum.DOWNLOADING

    def tick(self):
        """Call this to start/stop the fake progress task.

        It is more efficient as a `tick` hook than something we do on every state change.
        """
        if not self.is_downloading:
            self.fake_progress_task.discard()
            return

        if self.fake_progress_task.done():
            self.fake_progress_task.discard()

        self.fake_progress_task.schedule()

    async def fake_progress(self):
        while not self.is_stopped() and self.is_downloading:
            print("FAKE PROGRESS")
            self.client.printer.file_progress.model_set_changed("state", "progress")
            await self.wait(self.backoff.delay())
