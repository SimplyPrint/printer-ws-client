import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from typing import (Any, Callable, Generic, Iterable, List,
                    Optional, Tuple, TypeVar, Union, Dict, Coroutine)

import sys
import time

from ..client import Client, ClientConfigChangedEvent
from ..config.config import Config
from ..config.manager import ConfigManager
from ..connection import (Connection, ConnectionConnectedEvent,
                          ConnectionDisconnectEvent,
                          ConnectionEventReceivedEvent,
                          ConnectionReconnectEvent)
from ..events.client_events import (ClientEvent)
from ..events.demand_events import DemandEvent
from ..events.event_bus import Event, EventBus
from ..events.server_events import ServerEvent
from ..helpers.sentry import Sentry

TClient = TypeVar("TClient", bound=Client)
TConfig = TypeVar("TConfig", bound=Config)


class InstanceException(RuntimeError):
    ...


class Instance(ABC, Generic[TClient, TConfig]):
    """

    Abstract instance of a SimplyPrint client. This class
    contains the big picture stuff for controlling any amounts
    of clients, excluding the management of the clients themselves.

    The general workflow and responsibilities of an instance is as follows:

    1. Maintain connection to websocket server when applicable.
    2. Consume events from the websocket server.
    3. Broker events to the appropriate clients.
    4. Broker events from clients to the websocket server.
    5. Progress client "tick" when applicable.


    """

    logger = logging.getLogger("instance")

    sentry: Optional[Sentry] = None

    url: Optional[str] = None
    connection: Connection
    config_manager: ConfigManager[TConfig]

    allow_setup = False
    reconnect_timeout: float = 5.0
    tick_rate: float = 1.0

    # Allow supervisor to keep track of the last time the instance ticked
    heartbeat: float = 0.0

    event_bus: EventBus[Event]

    _loop: Optional[asyncio.AbstractEventLoop] = None

    # Allow the instance to be stopped
    _stop_event: threading.Event

    # Ensure the instance can only be started once.
    _instance_lock: threading.Lock
    _instance_thread_id: Optional[int] = None

    # Ensure we only allow one disconnect event to be processed at a time
    disconnect_lock: asyncio.Lock

    # Queues to synchronize events between threads / coroutines
    server_event_backlog: List[Tuple[ConnectionEventReceivedEvent]]
    client_event_backlog: List[Tuple[TClient, ClientEvent]]

    def __init__(self, config_manager: ConfigManager[TConfig], allow_setup=False,
                 reconnect_timeout=5.0, tick_rate=1.0) -> None:
        self.config_manager = config_manager

        self._stop_event = threading.Event()
        self._instance_lock = threading.Lock()

        self.event_bus = EventBus()

        self.server_event_backlog = []
        self.client_event_backlog = []

        self.allow_setup = allow_setup
        self.reconnect_timeout = reconnect_timeout
        self.tick_rate = tick_rate

        self.event_bus.on(ServerEvent, self.on_event, generic=True)

        self.reset_connection()

    def set_url(self, url: str) -> None:
        self.url = url

    def reset_connection(self):
        self.connection = Connection()

        self.connection.event_bus.on(ConnectionConnectedEvent, self.on_connect)
        self.connection.event_bus.on(
            ConnectionDisconnectEvent, self.on_disconnect)
        self.connection.event_bus.on(
            ConnectionReconnectEvent, self.on_reconnect)
        self.connection.event_bus.on(
            ConnectionEventReceivedEvent, self.on_received_event)

        self.disconnect_lock = asyncio.Lock()

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """
        Get the event loop for the client.
        """

        if not self._loop:
            raise RuntimeError("Loop not initialized")

        return self._loop

    async def __aenter__(self):
        if self._instance_thread_id is not None and self._instance_thread_id != threading.get_ident():
            self.logger.warning("Instance already started - waiting for it to stop")

        self._instance_lock.acquire()

        self._instance_thread_id = threading.get_ident()

        self._loop = asyncio.get_running_loop()

        if self.sentry and self.sentry.sentry_dsn is not None:
            self.sentry.initialize_sentry()

        # Reset the stop event
        self._stop_event.clear()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._loop = None
        self._stop_event.set()
        self.reset_connection()
        # Initialize a new connection
        self._instance_thread_id = None

        self._instance_lock.release()

    async def run(self) -> None:
        """ Only call this method once per thread."""
        if not self._instance_lock.locked() or self._instance_thread_id != threading.get_ident():
            raise InstanceException("Instance.run() can only run inside its context manager")

        await asyncio.gather(
            self.poll_events(),
            self.consume_clients()
        )

    def is_healthy(self, max_heartbeats_missed=2) -> bool:
        """ This function is intended to be available to the implementer to check if the instance is healthy."""

        # While the instance is stopped or not started, it is considered healthy
        if self._stop_event.is_set():
            return True

        # While not connected, the instance is considered healthy
        if not self.connection.is_connected():
            return True

        return time.time() - self.heartbeat < self.tick_rate * max_heartbeats_missed

    def stop(self) -> None:
        _ = self.get_loop().create_task(self.connection.close_internal())
        self._stop_event.set()

    async def consume_clients(self):
        client_tasks: Dict[TClient, Tuple[asyncio.Task, float]] = {}

        while not self._stop_event.is_set():
            dt = time.time()

            try:
                if not self.connection.is_connected():
                    self.logger.debug("Consuming clients - not connected")
                    await asyncio.sleep(self.reconnect_timeout)
                    await self.connection.event_bus.emit(ConnectionDisconnectEvent())
                    continue

                for client in self.get_clients():
                    prev_task, started_at = client_tasks.get(client, (None, None))

                    if prev_task is not None and not prev_task.done():
                        if time.time() - started_at > self.tick_rate:
                            client.logger.warning(
                                f"Client tick took longer than {self.tick_rate} seconds")

                        continue

                    task = self.get_loop().create_task(self.consume_client(client))
                    client_tasks[client] = (task, time.time())

                await asyncio.sleep(max(0.0, self.tick_rate - (time.time() - dt)))

            except Exception as e:
                self.logger.exception(e)

            self.heartbeat = time.time()

        # Stop all clients
        for client in list(self.get_clients()):
            self.stop_client_deferred(client)

        self.logger.info("Stopped consuming clients")

    @staticmethod
    async def consume_client(client: TClient, timeout: float = 5.0) -> None:
        # Only consume connected clients
        if not client.connected:
            client.logger.debug(f"Client not connected - not consuming")
            return

        try:
            async with asyncio.timeout(timeout):
                await client.tick()

        except asyncio.TimeoutError:
            client.logger.warning(f"Client timed out while ticking")

        events_to_process = client.printer.get_dirty_events()

        try:
            async with asyncio.timeout(timeout):
                await client.consume_state()

        except asyncio.TimeoutError:
            client.logger.warning(f"Client timed out while consuming state {events_to_process}")

    async def poll_events(self) -> None:
        while not self._stop_event.is_set():
            if not self.connection.is_connected():
                self.logger.debug("Not connected - not polling events")
                await asyncio.sleep(self.reconnect_timeout)
                await self.connection.event_bus.emit(ConnectionDisconnectEvent())
                continue

            await self.connection.poll_event()

        await self.connection.close_internal()
        self.logger.info("Stopped polling events")

    async def connect(self) -> None:
        if not self.should_connect():
            self.logger.info("No clients to connect - not connecting")
            return

        if self.connection.is_connected():
            self.logger.info(
                "Already connected - not connecting, call connection connect manually to force a reconnect")
            return

        await self.connection.connect(url=self.url)

    async def on_disconnect(self, _: ConnectionDisconnectEvent):
        async with self.disconnect_lock:
            if self._stop_event.is_set():
                return

            if self.connection.is_connected():
                return

            # Mark all printers as disconnected
            for client in self.get_clients():
                client.connected = False

            self.logger.info(
                f"Disconnected from server - reconnecting in {self.reconnect_timeout} seconds")

            await asyncio.sleep(self.reconnect_timeout)

            await self.connect()

    async def on_received_event(self, event: ConnectionEventReceivedEvent):
        """
        Events received by SimplyPrint to be ingested.
        """

        if event.for_client is None:
            # Internal event
            return

        if isinstance(event.for_client, str):
            config = Config(unique_id=event.for_client)
        else:
            config = Config(id=event.for_client)

        client = self.get_client(config)

        if not client:
            self.server_event_backlog.append((event,))
            return

        await self.event_bus.emit(event.event, client)

    def on_client_config_changed(self, client: TClient):
        """ 
        When a client config is changed, persist it to disk.
        """

        self.config_manager.flush(client.config)

    def stop_client_deferred(self, client: TClient):
        """
        Stops a client, but does not wait for it to stop.

        Can perform complex operations such as saving state to disk.
        Or operating on other threads and IO.
        """

        self.logger.info(f"Stopping client {client.config.unique_id} in the background")

        def stop_client(c: TClient):
            asyncio.run(c.stop())
            sys.exit(0)

        threading.Thread(target=stop_client, args=(client,), daemon=True).start()

    async def delete_client(self, client: TClient):
        """
        Deletes a client from the instance.
        """

        if not self.has_client(client):
            raise InstanceException("Client not registered")

        self.config_manager.remove(client.config)
        self.config_manager.flush()

        await self.remove_client(client)

        # Client stop might be blocking.
        self.stop_client_deferred(client)

    async def register_client(self, client: TClient):
        """
        Adds some default event handling for a client.
        should be called once.
        """

        if self.has_client(client):
            raise InstanceException("Client already registered")

        if not client.config.unique_id:
            raise InstanceException("Client has no unique id")

        self.config_manager.persist(client.config)
        self.config_manager.flush(client.config)

        # Capture generic client events to be sent to SimplyPrint
        async def on_client_event(event: ClientEvent):
            await self.on_client_event(event, client)

        client.event_bus.on(ClientEvent, on_client_event, generic=True)

        def on_client_config_changed(_: ClientConfigChangedEvent):
            self.on_client_config_changed(client)

        # Listen to custom events for internal use.
        client.event_bus.on(ClientConfigChangedEvent, on_client_config_changed)

        await self.add_client(client)
        await self.consume_backlog(self.server_event_backlog, self.on_received_event)

        if not self.connection.is_connected():
            await self.connect()

        await client.init()

        client.printer.mark_all_changed_dirty()

    @staticmethod
    async def consume_backlog(backlog: List[Tuple[Any, ...]],
                              consumer: Callable[[Any, ...], Coroutine[Any, Any, None]]):
        """
        Consumes any events that were received before the client was registered
        this will push elements still not consumed to the end of the list,
        so we keep track of the seek pointer
        """

        seek_pointer = 0
        seek_until = len(backlog)

        while seek_pointer < seek_until:
            args = backlog.pop(0)

            await consumer(*args)

            seek_pointer += 1

    async def on_event(self, event: Union[ServerEvent, DemandEvent], client: TClient):
        """
        Called when a client event is received.

        Do not wait for client handlers to run as they will block the event loop.
        """

        if not isinstance(event, ServerEvent):
            raise InstanceException(f"Expected ServerEvent but got {event}")

        _ = self.get_loop().create_task(client.event_bus.emit(event))

    async def on_client_event(self, event: ClientEvent, client: Client[TConfig]):
        """
        Called when a client event is received.
        """

        if not isinstance(event, ClientEvent):
            raise InstanceException(f"Expected ClientEvent but got {event}")

        # If the client is in setup only a certain subset of events is allowed
        if client.config.in_setup and not event.event_type.is_allowed_in_setup():
            return

        await self.connection.send_event(client, event)

    @abstractmethod
    def get_clients(self) -> Iterable[TClient]:
        """
        Returns an iterable of all clients that should be considered "active".
        """
        ...

    @abstractmethod
    def has_client(self, client: TClient) -> bool:
        """
        Returns true if the instance has a client.
        """
        ...

    @abstractmethod
    def get_client(self, config: TConfig) -> Optional[TClient]:
        """
        Returns a client instance for the given config, potentially partial config.
        """
        ...

    @abstractmethod
    async def add_client(self, client: TClient) -> None:
        """
        Adds a client to the instance.
        """
        ...

    @abstractmethod
    async def remove_client(self, client: TClient) -> None:
        """
        Removes a client from the instance.
        """
        ...

    @abstractmethod
    def should_connect(self) -> bool:
        """
        Should return true if the instance should connect to the server.
        """
        ...

    @abstractmethod
    async def on_connect(self, _: ConnectionConnectedEvent):
        """
        Called the first time the connection is established.

        Here the appropriate startup logic for an instance can
        be implemented.
        """
        ...

    @abstractmethod
    async def on_reconnect(self, _: ConnectionReconnectEvent):
        """
        Called when the connection is re-established.

        Here it is the instances job to re-add any clients to the connection
        """
        ...
