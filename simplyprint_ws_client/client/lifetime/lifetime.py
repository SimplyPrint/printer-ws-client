import asyncio
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from ...utils.stoppable import AsyncStoppable

if TYPE_CHECKING:
    from ..client import Client


class ClientLifetime(AsyncStoppable, ABC):
    timeout_upper_bound = 60.0
    tick_rate_upper_bound = 10.0
    heartbeat_delta = 0.1

    client: "Client"
    timeout = 5.0
    tick_rate = 1.0

    last_ten_heartbeats: List[Optional[float]] = [None] * 10

    def __init__(self, client: "Client", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client

    @abstractmethod
    async def start(self):
        ...

    @abstractmethod
    def stop_deferred(self):
        ...

    def heartbeat(self):
        self.last_ten_heartbeats.pop(0)
        self.last_ten_heartbeats.append(time.time())

    def heartbeat_durations(self) -> List[float]:
        return [self.last_ten_heartbeats[i] - self.last_ten_heartbeats[i - 1] for i in range(1, 10) if
                self.last_ten_heartbeats[i - 1] is not None]

    def average_heartbeat_duration(self) -> Optional[float]:
        durations = self.heartbeat_durations()
        return sum(durations) / len(durations) if durations else None

    @staticmethod
    def increment_until_bound(value: float, increment: float, upper_bound: float) -> float:
        return min(value + increment, upper_bound)

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
            self.timeout = self.increment_until_bound(self.timeout, 1.0, self.timeout_upper_bound)

        events_to_process = self.client.printer.get_dirty_events()

        try:
            async with asyncio.timeout(self.timeout):
                await self.client.consume_state()

        except asyncio.TimeoutError:
            self.client.logger.warning(f"Client timed out while consuming state {events_to_process}")
            self.timeout = self.increment_until_bound(self.timeout, 1.0, self.timeout_upper_bound)

    def is_healthy(self, timeout: float = 0.0) -> bool:
        average_heartbeat_duration = self.average_heartbeat_duration()

        # Not enough heartbeats to calculate average
        if average_heartbeat_duration is None:
            return True

        if average_heartbeat_duration > self.tick_rate + self.heartbeat_delta:
            self.tick_rate = self.increment_until_bound(self.tick_rate, self.heartbeat_delta,
                                                        self.tick_rate_upper_bound)

            self.client.logger.warning(
                f"Client is almost unhealthy: average heartbeat duration is {average_heartbeat_duration} " +
                f"incrementing to keep up, tick rate is now at {self.tick_rate}"
            )

        # We are healthy if the average heartbeat duration is less than the tick rate + timeout
        return average_heartbeat_duration < self.tick_rate + timeout

    async def loop(self):
        while not self.is_stopped():
            dt = time.time()

            try:
                await self.consume()
            except Exception as e:
                self.client.logger.error("An error occurred while consuming the client", exc_info=e)
            finally:
                self.heartbeat()
                await self.wait(max(0.0, self.tick_rate - (time.time() - dt)))

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
    async_task: Optional[asyncio.Task] = None

    def stop_deferred(self):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.client.logger.info(f"Stopping client in the background")
        threading.Thread(target=asyncio.run, args=(self.client.stop(),)).start()

    async def start(self):
        if self.async_task and not self.async_task.done():
            # Await the task to ensure it is stopped
            await self.async_task

        self.async_task = asyncio.create_task(self.loop())
