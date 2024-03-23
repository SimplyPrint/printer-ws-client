import asyncio
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ...utils.stoppable import AsyncStoppable

if TYPE_CHECKING:
    from ..client import Client


class ClientLifetime(AsyncStoppable, ABC):
    client: "Client"

    timeout = 5.0
    tick_rate = 1.0
    heartbeat = 0.0

    def __init__(self, client: "Client", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client

    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    def stop_deferred(self):
        ...

    async def consume(self):
        # Only consume connected clients
        if not self.client.connected:
            self.client.logger.debug(f"Client not connected - not consuming")
            return

        try:
            async with asyncio.timeout(self.timeout):
                await self.client.tick()

        except asyncio.TimeoutError:
            self.client.logger.warning(f"Client timed out while ticking")

        events_to_process = self.client.printer.get_dirty_events()

        try:
            async with asyncio.timeout(self.timeout):
                await self.client.consume_state()

        except asyncio.TimeoutError:
            self.client.logger.warning(f"Client timed out while consuming state {events_to_process}")

    def is_healthy(self, timeout: float = 0.0) -> bool:
        return self.heartbeat + timeout > time.time()

    async def loop(self):
        while not self.is_stopped():
            dt = time.time()

            try:
                await self.consume()
            except Exception as e:
                self.client.logger.exception(e)

            await self.wait(max(0.0, self.tick_rate - (time.time() - dt)))
            self.heartbeat = time.time()

        # Client implements custom stop logic
        self.stop_deferred()


"""

class ClientSyncLifetime(ClientLifetime, EventLoopProvider[asyncio.AbstractEventLoop], SyncStoppable):
    loop_thread: threading.Thread

    def stop_deferred(self):
        self.client.logger.info(f"Stopping client")
        asyncio.run_coroutine_threadsafe(self.client.stop(), self.event_loop)

    async def loop(self):
        self.use_running_loop()
        await super().loop()
        self.reset_event_loop()

    async def start(self):
        def main():
            with EventLoopRunner() as runner:
                runner.run(self.loop)

        self.loop_thread = threading.Thread(target=main)
        self.loop_thread.start()

    def stop(self):
        super().stop()
        self.loop_thread.join()
"""


class ClientAsyncLifetime(ClientLifetime, AsyncStoppable):
    async_task: asyncio.Task

    def stop_deferred(self):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.client.logger.info(f"Stopping client in the background")
        threading.Thread(target=asyncio.run, args=(self.client.stop(),)).start()

    async def start(self):
        self.async_task = asyncio.create_task(self.loop())
