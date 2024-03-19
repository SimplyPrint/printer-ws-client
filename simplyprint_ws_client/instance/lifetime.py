import asyncio
import threading
from typing import Generic, Dict

from .instance import TClient
from ..helpers.stoppable import AsyncStoppable, SyncStoppable


class InstanceClientLifetime(Generic[TClient], AsyncStoppable):
    client: TClient

    timeout = 5.0
    tick_rate = 1.0
    heartbeat = 0.0

    def __init__(self, client: TClient):
        super().__init__()
        self.client = client

    def stop_deferred(self):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.client.logger.info(f"Stopping client in the background")

        def stop_client(c: TClient):
            asyncio.run(c.stop())

        threading.Thread(target=stop_client, args=(self.client,)).start()

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


class InstanceLifetimeManager(Generic[TClient], SyncStoppable):
    lifetimes: Dict[TClient, InstanceClientLifetime[TClient]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ...

    async def loop(self):
        client_tasks: Dict[TClient, Tuple[asyncio.Task, float]] = {}

        while not self.is_stopped():
            dt = time.time()

            try:
                if not self.connection.is_connected():
                    self.logger.debug("Consuming clients - not connected")
                    await self.connection.event_bus.emit(ConnectionDisconnectEvent())
                    raise InstanceException("Not connected - not consuming clients")

                for client in self.get_clients():
                    prev_task, started_at = client_tasks.get(client, (None, None))

                    if prev_task is not None and not prev_task.done():
                        if time.time() - started_at > self.tick_rate:
                            client.logger.warning(
                                f"Client tick took longer than {self.tick_rate} seconds")

                        continue

                    task = self.get_loop().create_task(self.consume_client(client))
                    client_tasks[client] = (task, time.time())

            except InstanceException:
                # Jump to end.
                pass
            except Exception as e:
                self.logger.exception(e)
            finally:
                await asyncio.sleep(max(0.0, self.tick_rate - (time.time() - dt)))
                self.heartbeat = time.time()

        # Stop all clients
        for client in list(self.get_clients()):
            self.stop_client_deferred(client)

        self.logger.info("Stopped consuming clients")
