import asyncio
import threading
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from ...utils.bounded_variable import BoundedInterval
from ...utils.stoppable import AsyncStoppable

if TYPE_CHECKING:
    from ..client import Client
    from .lifetime_manager import LifetimeManager
    from ...utils.bounded_variable import BoundedVariable

# Bounds for the client lifetime
TimeoutBoundedInterval: BoundedInterval[float] = BoundedInterval(60.0, 1.0, default=5.0)
TickRateBoundedInterval: BoundedInterval[float] = BoundedInterval(10.0, 0.1, default=1.0)

# Space warning out 10 ticks before warning about connected state to prevent log spamming
ConsumeBeforeWarningBoundedInterval: BoundedInterval[int] = BoundedInterval(10, 1, default=10)


class ClientLifetime(AsyncStoppable, ABC):
    heartbeat_delta = 0.5

    client: "Client"
    parent: "LifetimeManager"
    timeout: "BoundedVariable[float]"
    tick_rate: "BoundedVariable[float]"
    consume_warning: "BoundedVariable[int]"

    last_ten_heartbeats: List[Optional[float]] = [None] * 10

    def __init__(self, parent: "LifetimeManager", client: "Client"):
        super().__init__(parent_stoppable=parent)
        self.client = client
        self.parent = parent
        self.timeout = TimeoutBoundedInterval.create_variable()
        self.tick_rate = TickRateBoundedInterval.create_variable()
        self.consume_warning = ConsumeBeforeWarningBoundedInterval.create_variable()

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

        # Only start counting when we have enough heartbeats
        return sum(durations) / len(durations) if len(durations) > 5 else None

    async def consume(self):
        # If the parent context (LifetimeManager) does not want us to consume, we don't
        # for instance when we are globally disconnected.
        if not self.parent.should_consume(self.client):
            return

        # Only consume connected clients
        if not self.client.connected:
            if self.consume_warning.guard_until_bound():
                self.client.logger.warning(
                    f"Client not connected {self.client.config.unique_id=} {self.client._connected=} {self.client.connected=} - still consuming this is an error.")
            return

        try:
            async with asyncio.timeout(self.timeout.value):
                await self.client.tick()

        except asyncio.TimeoutError:
            self.client.logger.warning(f"Client timed out while ticking")
            self.timeout.increment()

        events_to_process = self.client.printer.get_dirty_events()

        try:
            async with asyncio.timeout(self.timeout.value):
                await self.client.consume_state()

        except asyncio.TimeoutError:
            self.client.logger.warning(f"Client timed out while consuming state {events_to_process}")
            self.timeout.increment()

    def is_healthy(self) -> bool:
        average_heartbeat_duration = self.average_heartbeat_duration()

        # Not enough heartbeats to calculate average
        if average_heartbeat_duration is None:
            return True

        if average_heartbeat_duration > self.tick_rate.value + self.heartbeat_delta:
            self.tick_rate.increment()

            self.client.logger.warning(
                f"Client is almost unhealthy: average heartbeat duration is {average_heartbeat_duration} " +
                f"incrementing to keep up, tick rate is now at {self.tick_rate.value}"
            )

        # We are healthy if the average heartbeat duration is less than the tick rate + timeout
        # We allow the tick rate to progress up to the timeout.
        if self.tick_rate.is_at_bound() and not average_heartbeat_duration < self.tick_rate.value + self.timeout.value:
            self.client.logger.warning(
                f"Client is unhealthy: average heartbeat duration is {average_heartbeat_duration} " +
                f"expected less than {self.tick_rate.value + self.timeout.value}"
            )

            return False

        # Reset the tick rate if we have been healthy for a while.
        if self.tick_rate.is_at_bound() and average_heartbeat_duration < self.tick_rate.default:
            self.tick_rate.reset()

        return True

    async def loop(self):
        self.client.logger.info(f"Starting client lifetime loop")

        while not self.is_stopped():
            t = time.time()

            try:
                await self.consume()
            except Exception as e:
                self.client.logger.error("An error occurred while consuming the client", exc_info=e)
            finally:
                self.heartbeat()
                dt = max(0.0, self.tick_rate.value - (time.time() - t))
                await self.wait(dt)

        self.client.logger.info(f"Client lifetime loop stopped")
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
    _start_lock: asyncio.Lock
    _async_task: Optional[asyncio.Task] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_lock = asyncio.Lock()

    def stop_deferred(self):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.client.logger.info(f"Stopping client in the background")
        threading.Thread(target=asyncio.run, args=(self.client.stop(),), daemon=True).start()

    async def start(self):
        loop = asyncio.get_running_loop()

        async with self._start_lock:
            if self._async_task and not self._async_task.done():
                # Await the task to ensure it is stopped
                self.client.logger.debug("Cannot start lifetime while previous loop is still running. Waiting.")
                await self._async_task

            # Initialize client
            await self.client.init()

            # SAFETY: This does not leak as it does not run forever.
            self._async_task = loop.create_task(self.loop())
