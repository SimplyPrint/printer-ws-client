import asyncio
import functools
import logging
import threading
from abc import ABC, abstractmethod
from typing import (Any, Callable, Generic, Iterable, List,
                    Optional, Tuple, TypeVar, Union, Coroutine)

from ..client import Client, ClientConfigChangedEvent
from ..config.config import PrinterConfig
from ..config.manager import ConfigManager
from ..lifetime.lifetime_manager import LifetimeManager, LifetimeType
from ...connection.connection import (Connection, ConnectionConnectedEvent,
                                      ConnectionDisconnectEvent,
                                      ConnectionPollEvent,
                                      )
from ...events.client_events import (ClientEvent)
from ...events.demand_events import DemandEvent
from ...events.event_bus import Event, EventBus
from ...events.server_events import ServerEvent, ConnectEvent
from ...utils.event_loop_provider import EventLoopProvider
from ...utils.stoppable import AsyncStoppable, Stoppable

TClient = TypeVar("TClient", bound=Client)
TConfig = TypeVar("TConfig", bound=PrinterConfig)


class InstanceException(RuntimeError):
    ...


class Instance(AsyncStoppable, EventLoopProvider, Generic[TClient, TConfig], ABC):
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

    url: Optional[str] = None
    connection: Connection

    config_manager: ConfigManager[TConfig]
    lifetime_manager: LifetimeManager

    allow_setup = False
    reconnect_timeout: float = 5.0

    event_bus: EventBus[Event]

    # Ensure the instance can only be started once.
    __instance_lock: threading.Lock
    # Ensure calls to stop are thread safe.
    __instance_stop_lock: threading.Lock
    # Ensure the instance is only started once.
    __instance_thread_id: Optional[int] = None

    # Allow logic to wait until ws-connection responds with ready message.
    connection_is_ready: Optional[asyncio.Event] = None

    # Ensure we only allow one disconnect event to be processed at a time
    disconnect_lock: asyncio.Lock

    # Queues to synchronize events between threads / coroutines
    server_event_backlog: List[Tuple[ConnectionPollEvent]]
    client_event_backlog: List[Tuple[TClient, ClientEvent]]

    def __init__(self, config_manager: ConfigManager[TConfig], allow_setup=False,
                 reconnect_timeout=5.0) -> None:

        super().__init__()

        self.config_manager = config_manager
        self.lifetime_manager = LifetimeManager(self, parent_stoppable=self)

        self.__instance_lock = threading.Lock()
        self.__instance_stop_lock = threading.Lock()

        self.event_bus = EventBus()

        self.server_event_backlog = []
        self.client_event_backlog = []

        self.allow_setup = allow_setup
        self.reconnect_timeout = reconnect_timeout

        self.event_bus.on(ServerEvent, self.on_server_event, generic=True)

        self.reset_connection()

    def set_url(self, url: str) -> None:
        self.url = url

    def reset_connection(self):
        self.connection = Connection(event_loop_provider=self)

        self.connection.event_bus.on(ConnectionConnectedEvent, self.on_connect)
        self.connection.event_bus.on(
            ConnectionDisconnectEvent, self.on_disconnect)

        self.connection.event_bus.on(
            ConnectionPollEvent, self.on_poll_event)

        self.connection_is_ready = asyncio.Event()
        self.disconnect_lock = asyncio.Lock()

    async def __aenter__(self):
        if self.__instance_thread_id is not None and self.__instance_thread_id != threading.get_ident():
            self.logger.warning("Instance already started - waiting for it to stop")

        self.__instance_lock.acquire()

        self.__instance_thread_id = threading.get_ident()

        self.use_running_loop()

        # Reset the stop event
        self.clear()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.reset_event_loop()

        # Set the stop event
        with self.__instance_stop_lock:
            Stoppable.stop(self)

        self.reset_connection()
        # Initialize a new connection
        self.__instance_thread_id = None
        self.__instance_lock.release()

    async def run(self) -> None:
        """ Only call this method once per thread."""
        if not self.__instance_lock.locked() or self.__instance_thread_id != threading.get_ident():
            raise InstanceException("Instance.run() can only run inside its context manager")

        # Initial connect we cannot block until connected is
        # received as we will never poll any events if this blocks.
        await self.connect(block_until_connected=False)

        await asyncio.gather(
            self.poll_events(),
            self.lifetime_manager.loop()
        )

    def stop(self) -> None:
        async def async_stop():
            self.logger.info("Stopping instance")

            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            await asyncio.gather(*tasks, return_exceptions=True)

            self.logger.info("Stopped instance")

        # Asyncio event is not threadsafe.
        def locked_stop():
            with self.__instance_stop_lock:
                Stoppable.stop(self)

        if self.event_loop_is_running():
            asyncio.run_coroutine_threadsafe(async_stop(), self.event_loop)
            self.event_loop.call_soon_threadsafe(locked_stop)
        else:
            self.logger.warning("Event loop not running - stopping instance synchronously.")
            locked_stop()

    async def poll_events(self) -> None:
        loop = asyncio.get_running_loop()

        # SAFETY: This does leak as this task is bounded by the loop, so when the loop exists it is done.
        wait_task = loop.create_task(self.wait())

        while not self.is_stopped():
            if not self.connection.is_connected():
                self.logger.debug("Not connected - not polling events")
                await self.event_bus.emit(ConnectionDisconnectEvent())

                # If we are not connected yet just wait the timeout anyhow
                # to prevent a tight loop.
                if not self.connection.is_connected():
                    await self.wait(1.0)

                continue

            await asyncio.wait([
                wait_task,
                # SAFETY: This event either completes first, or we leak a single instance.
                loop.create_task(self.connection.poll_event())
            ], return_when=asyncio.FIRST_COMPLETED)

        await self.connection.close_internal()
        self.logger.info("Stopped polling events")

    async def connect(self, ignore_connect_criteria=False, block_until_connected=True) -> None:
        if self.is_stopped():
            self.logger.info("Instance stopped - not connecting")
            return

        if not ignore_connect_criteria and not self.should_connect():
            self.logger.info("No clients to connect - not connecting")
            return

        if self.connection.is_connected():
            self.logger.info(
                "Already connected - not connecting, call connection connect manually to force a reconnect")
            return

        await self.connection.connect(url=self.url, allow_reconnects=False)

        if block_until_connected:
            # Wait until the first connect event is received
            await self.connection_is_ready.wait()

    async def on_disconnect(self, _: ConnectionDisconnectEvent):
        async with self.disconnect_lock:
            if self.is_stopped() or self.connection.is_connected():
                self.logger.debug("Still connected somehow so we are not reconnecting")
                return

            # Reset the waiter
            self.connection_is_ready.clear()

            if not self.should_connect():
                self.logger.debug("No clients to reconnect so we stay disconnected.")
                return

            # Mark all printers as disconnected
            for client in self.get_clients():
                async with client:
                    client.connected = False

            self.logger.info(
                f"Disconnected from server - reconnecting in {self.reconnect_timeout} seconds")

            await self.wait(self.reconnect_timeout)

            # If reconnections fails, connect dispatches a new event
            # which runs in another coroutine, so on_disconnect should not block
            # the disconnect lock, so that another task can take over, other tasks
            # will block on connect until another task has made the connection.
            await self.connect(block_until_connected=False)

    async def on_poll_event(self, event: ConnectionPollEvent):
        """
        Events received by SimplyPrint to be ingested.
        """

        if isinstance(event.for_client, str):
            client = self.get_client(unique_id=event.for_client)
        else:
            client = self.get_client(id=event.for_client)

        if not client and event.event == ConnectEvent:
            self.connection_is_ready.set()

        if not client or self.is_stopped():
            if event.allow_backlog:
                self.server_event_backlog.append((event,))

            return

        await self.event_bus.emit(event.event, client)

    def on_client_config_changed(self, client: TClient):
        """
        When a client config is changed, persist it to disk.
        """

        self.config_manager.flush(client.config)

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

        # Listen to custom events for internal use.
        client.event_bus.on(ClientConfigChangedEvent, functools.partial(self.on_client_config_changed, client))

        try:
            await self.add_client(client)
        except InstanceException:
            raise

        await self.consume_backlog(self.server_event_backlog, self.on_poll_event)

        client.printer.mark_all_changed_dirty()

        self.lifetime_manager.add(client, LifetimeType.ASYNC)
        await self.lifetime_manager.start_lifetime(client)

    async def deregister_client(self, client: TClient, remove_from_config=False):
        """
        Deletes a client from the instance.
        """

        if not self.has_client(client):
            raise InstanceException("Client not registered")

        if remove_from_config:
            self.config_manager.remove(client.config)
            self.config_manager.flush()

        await self.remove_client(client)

        # Client stop might be blocking.
        self.lifetime_manager.remove(client)

    @staticmethod
    async def consume_backlog(backlog: List[Tuple[Any, Any]],
                              consumer: Callable[[Any, Any], Coroutine[Any, Any, None]]):
        """
        Consumes any events that were received before the client was registered
        this will push elements still not consumed to the end of the list,
        so we keep track of the seek pointer
        """

        seek_pointer = 0
        seek_until = len(backlog)

        while seek_pointer < seek_until and len(backlog) > 0:
            args = backlog.pop(0)

            await consumer(*args)

            seek_pointer += 1

    async def on_server_event(self, event: Union[ServerEvent, DemandEvent], client: TClient):
        """
        Called when a client event is received.

        Do not wait for client handlers to run as they will block the event loop.
        """

        if self.is_stopped():
            raise InstanceException(f"Instance stopped - dropping event {event}.")

        if not isinstance(event, ServerEvent):
            raise InstanceException(f"Expected ServerEvent but got {event}")

        # SAFETY: This is potentially dangerous, but is limited by incoming events.
        _ = self.event_loop.create_task(client.event_bus.emit(event))

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
    def get_client(self, config: Optional[TConfig] = None, **kwargs) -> Optional[TClient]:
        """
        Returns a client instance for the given filter arguments, potentially partial args.
        """
        ...

    @abstractmethod
    async def add_client(self, client: TClient) -> None:
        """Internal
        Adds a client to the instance.
        """
        ...

    @abstractmethod
    async def remove_client(self, client: TClient) -> None:
        """ Internal
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
