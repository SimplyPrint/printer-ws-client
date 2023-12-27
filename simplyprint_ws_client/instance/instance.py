import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop
from typing import (Any, Awaitable, Callable, Generic, Iterable, List,
                    Optional, Tuple, TypeVar, Union)

from flask import config

from ..client import Client, ClientConfigChangedEvent
from ..config.config import Config
from ..config.manager import ConfigManager
from ..connection import (Connection, ConnectionConnectedEvent,
                          ConnectionDisconnectEvent,
                          ConnectionEventReceivedEvent,
                          ConnectionReconnectEvent)
from ..events.client_events import (ALLOWED_IN_SETUP, ClientEvent,
                                    MachineDataEvent, StateChangeEvent)
from ..events.demands import DemandEvent
from ..events.event_bus import Event, EventBus
from ..events.server_events import ServerEvent
from ..helpers.sentry import Sentry

TClient = TypeVar("TClient", bound=Client)
TConfig = TypeVar("TConfig", bound=Config)

class InstanceException(Exception):
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

    loop: AbstractEventLoop
    sentry: Optional[Sentry] = None
    connection: Connection
    config_manager: ConfigManager[TConfig]

    allow_setup = False
    reconnect_timeout: float = 5.0
    tick_rate: float = 1.0

    _stop_event: threading.Event

    event_bus: EventBus[Event]

    # Queues to synchronize events between threads / coroutines
    server_event_backlog: List[Tuple[ConnectionEventReceivedEvent]]
    client_event_backlog: List[Tuple[TClient, ClientEvent]]

    def __init__(self, loop: AbstractEventLoop, config_manager: ConfigManager[TConfig], allow_setup = False, reconnect_timeout = 5.0, tick_rate = 1.0) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self.connection = Connection(self.loop)
        self.config_manager = config_manager

        self.connection.event_bus.on(ConnectionConnectedEvent, self.on_connect)
        self.connection.event_bus.on(ConnectionDisconnectEvent, self.on_disconnect)
        self.connection.event_bus.on(ConnectionReconnectEvent, self.on_reconnect)
        self.connection.event_bus.on(ConnectionEventReceivedEvent, self.on_recieved_event)

        self._stop_event = threading.Event()
        self.event_bus = EventBus()
        
        self.server_event_backlog = []
        self.client_event_backlog = []

        self.allow_setup = allow_setup
        self.reconnect_timeout = reconnect_timeout
        self.tick_rate = tick_rate

        self.event_bus.on_generic(ServerEvent, self.on_event)

    async def run(self) -> None:        
        if self.sentry and self.sentry.sentry_dsn is not None:
            self.sentry.initialize_sentry()
        
        if not self.connection.is_connected():
            await self.connect()

        await asyncio.gather(
            self.poll_events(),
            self.consume_clients()
        )

    def stop(self) -> None:
        self._stop_event.set()
        self.loop.stop()

    async def consume_clients(self):
        while not self._stop_event.is_set():
            dt = time.time()

            try:
                if not self.connection.is_connected():
                    await asyncio.sleep(self.reconnect_timeout)
                    continue

                for client in self.get_clients():
                    await self.consume_client(client)

                await asyncio.sleep(max(0, self.tick_rate - (time.time() - dt)))
                
            except Exception as e:
                self.logger.exception(e)

        # Stop all clients
        for client in self.get_clients():
            await client.stop()

    async def consume_client(self, client: TClient):
        # Only consume connected clients
        if not client.connected:
            return

        await client.tick()
        await client.consume_state()

    async def poll_events(self) -> None:
        while not self._stop_event.is_set():
            if not self.connection.is_connected():
                await asyncio.sleep(self.reconnect_timeout)
                continue

            await self.connection.poll_event()

    async def connect(self) -> None:
        if not self.should_connect():
            self.logger.info("No clients to connect - not connecting")
            return
        
        if self.connection.is_connected():
            self.logger.info("Already connected - not connecting, call connection connect manually to force a reconnect")
            return

        await self.connection.connect()

    async def on_disconnect(self, _: ConnectionDisconnectEvent):
        # Mark all printers as disconnected
        for client in self.get_clients():
            client.connected = False

        self.logger.info(f"Disconnected from server - reconnecting in {self.reconnect_timeout} seconds")
        await asyncio.sleep(self.reconnect_timeout)
        await self.connect()

    async def on_recieved_event(self, event: ConnectionEventReceivedEvent):
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

    async def on_client_config_changed(self, client: TClient):
        """ 
        When a client config is changed, persist it to disk.
        """

        self.config_manager.flush(client.config)

    async def delete_client(self, client: TClient):
        """
        Deletes a client from the instance.
        """

        if not self.has_client(client):
            raise InstanceException("Client not registered")

        await self.remove_client(client)
        
        self.config_manager.remove(client.config)
        self.config_manager.flush()
        
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

        # Capture generic client events to be sent to SimplyPrint
        async def on_client_event(event: ClientEvent):
            await self.on_client_event(client, event)
        
        client.event_bus.on_generic(ClientEvent, on_client_event)

        async def on_client_config_changed(_: ClientConfigChangedEvent):
            await self.on_client_config_changed(client)

        # Listen to custom events for internal use.
        client.event_bus.on(ClientConfigChangedEvent, on_client_config_changed)

        await self.add_client(client)
        await self.consume_backlog(self.server_event_backlog, self.on_recieved_event)
        
        if not self.connection.is_connected():
            await self.connect()

        await client.init()
    
        client.printer.mark_event_as_dirty(StateChangeEvent)
        client.printer.mark_event_as_dirty(MachineDataEvent)

    async def consume_backlog(self, backlog: List[Any], consumer: Callable[[Any], Awaitable[None]]):
        """
        Consumes any events that were received before the client was registered
        this will push elements still not consumed to the end of the list
        so we keep track of the seek pointer
        """

        seek_pointer = 0
        seek_until = len(backlog)

        while seek_pointer < seek_until:
            args = backlog.pop(0)

            await consumer(*args)

            seek_pointer += 1

    async def on_event(self, client: TClient, event: Union[ServerEvent, DemandEvent]):
        """
        Called when a client event is received.
        """

        await client.event_bus.emit(event)
    
    async def on_client_event(self, client: Client[TConfig], event: ClientEvent):
        """
        Called when a client event is received.
        """

        if not client.connected:
            self.client_event_backlog.append((client, event))
            return
        
        # If the client is in setup only a certain subset of events are allowed
        if client.config.in_setup and not event.event_type in ALLOWED_IN_SETUP: 
            return
        
        await self.connection.send_event(event)

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

