import asyncio
import threading
import time
from typing import Generic

from simplyprint_ws_client.client.instance.instance import TClient
from simplyprint_ws_client.utils.stoppable import AsyncStoppable


class ClientLifetime(Generic[TClient], AsyncStoppable):
    client: TClient

    timeout = 5.0
    tick_rate = 1.0
    heartbeat = 0.0

    def __init__(self, client: TClient, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client

    def stop_deferred(self):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.client.logger.info(f"Stopping client in the background")
        threading.Thread(target=asyncio.run, args=(self.client.stop(),)).start()

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

    async def loop(self):
        while not self.is_stopped():
            dt = time.time()

            try:
                await self.consume()
            except Exception as e:
                self.client.logger.exception(e)

            await asyncio.sleep(max(0.0, self.tick_rate - (time.time() - dt)))
            self.heartbeat = time.time()

        # Client implements custom stop logic
        self.stop_deferred()
