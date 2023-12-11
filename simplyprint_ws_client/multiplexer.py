import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional, Set, Tuple, Union

import aiohttp
import janus

from .client import Client
from .config import Config, ConfigManager
from .const import API_VERSION, WEBSOCKET_URL
from .events.client_events import ClientEvent, MachineDataEvent
from .events.events import ServerEvent
from .events.events import (ConnectEvent, MultiPrinterAddResponseEvent,
                            SetupCompleteEvent)
from .helpers.sentry import Sentry
from .websocket import SimplyPrintWebSocket


class MultiplexerException(RuntimeError):
    pass


class MultiplexerNotConnectedException(MultiplexerException):
    pass


class MultiplexerAlreadyConnectedException(MultiplexerException):
    pass


class MultiplexerConnectionFailedException(MultiplexerException):
    pass


class MultiplexerClientEvents(Enum):
    ADD_PRINTER = "add_connection"
    REMOVE_PRINTER = "remove_connection"


class MultiplexerAddPrinterEvent(ClientEvent):
    unique_set: Set[str] = set()

    event_type = MultiplexerClientEvents.ADD_PRINTER

    unique_id: str

    def __init__(self, config: Config, allow_setup: bool = False) -> None:
        if config.unique_id in self.unique_set:
            raise MultiplexerException(
                f"Cannot add printer with unique id {config.unique_id} as it is already in use")

        self.unique_id = config.unique_id
        self.unique_set.add(config.unique_id)

        super().__init__(None, None, {
            "pid": config.id,
            "token": config.token,
            "unique_id": config.unique_id,
            "allow_setup": allow_setup,
            "public_ip": config.public_ip,
        })


class MultiplexerRemovePrinterEvent(ClientEvent):
    event_type = MultiplexerClientEvents.REMOVE_PRINTER


class MultiplexerMode(Enum):
    MULTIPRINTER = "mp"
    SINGLE = "p"


class Multiplexer:
    """
    If multiplexer.start is run in a seperate thread, ensure the outer python programming
    is always running or is blocking otherwise the async thread will be unable to restart
    itself due to the executor being shutdown.
    """

    loop: asyncio.AbstractEventLoop

    connect_timeout: Optional[float]
    mode: MultiplexerMode = MultiplexerMode.SINGLE
    url: str

    ws: Optional[SimplyPrintWebSocket] = None

    clients: Dict[int, Client]
    pending_clients: Dict[str, Client]
    invalid_credentials: Dict[str, float]

    allow_setup: bool = False

    buffered_events: janus.Queue[Tuple[ServerEvent, Optional[int]]]
    update_queue: janus.Queue[Tuple[ServerEvent, Optional[int]]]
    event_queue: janus.Queue[ClientEvent]

    sentry: Sentry = Sentry()
    logger: logging.Logger = logging.getLogger("multiplexer")

    _connect_lock: asyncio.Lock = asyncio.Lock()
    _reconnect_lock: asyncio.Lock = asyncio.Lock()
    _disconnect_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, mode: MultiplexerMode, single_config: Optional[Config] = None, connect_timeout: Optional[float] = None):
        self.connect_timeout = connect_timeout or 1
        self.mode = mode
        self.url = self.get_url(single_config)

        self.clients = {}
        self.pending_clients = {}
        self.invalid_credentials = {}

    def get_url(self, config: Optional[Config] = None):
        return f"{WEBSOCKET_URL}/{API_VERSION}/{self.mode.value}" + (f"/{config.id}/{config.token}" if config is not None and config.id is not None and config.id != 0 else "/0/0")

    def get_single_client(self):
        if self.mode != MultiplexerMode.SINGLE:
            raise MultiplexerException(
                "Cannot get single client in multiplexer mode")

        if len(self.clients) + len(self.pending_clients) == 0:
            return None

        return (list(self.clients.values()) + list(self.pending_clients.values()))[0]

    def get_client_by_id(self, client_id: int):
        if self.mode == MultiplexerMode.SINGLE:
            # Always return the single client
            return self.get_single_client()

        if client_id in self.clients:
            return self.clients.get(client_id)

        # Linear search for client in pending clients
        for client in self.pending_clients.values():
            if client.config.id == client_id:
                return client

        return None

    def get_clients_by_token(self, token: str):
        return [client for client in self.clients.values() if client.config.token == token] + [client for _, client in self.pending_clients.values() if client.config.token == token]

    def _format_credentials_key(self, config: Config):
        return f"{config.id}:{config.token}"

    def add_client(self, client: Client, unique_id: Optional[str] = None, public_ip: Optional[str] = None):
        if self._format_credentials_key(client.config) in self.invalid_credentials:
            if time.time() - self.invalid_credentials[self._format_credentials_key(client.config)] < 60:
                raise MultiplexerConnectionFailedException(
                    "Cannot add client with invalid credentials")
            else:
                del self.invalid_credentials[self._format_credentials_key(
                    client.config)]

        if self.get_client_by_id(client.config.id) is not None and len(self.get_clients_by_token(client.config.token)) != 0:
            raise MultiplexerAlreadyConnectedException(
                f"Cannot add client with id {client.config.id} and token {client.config.token} as it is already connected")

        if unique_id is None and self.mode != MultiplexerMode.SINGLE:
            unique_id = str(id(client))

        async def client_send_handle(self, event: ClientEvent):
            event.for_client = client.config.id
            self.queue_event_sync(event)

        client.sentry = self.sentry
        client.send_event = lambda event: client_send_handle(self, event)
        client.printer.connected = False
        client.config.public_ip = public_ip
        client.config.unique_id = unique_id

        if self.mode == MultiplexerMode.SINGLE:
            assert len(self.clients) == 0, "Cannot add more than one client in single mode"
            self.clients[client.config.id] = client
            return

        self.pending_clients[unique_id] = client

        if self.is_connected():
            try:
                self.queue_event_sync(MultiplexerAddPrinterEvent(
                    client.config, allow_setup=self.allow_setup))
            except MultiplexerException:
                pass  # Already in the queue

        self.logger.debug(
            f"Added printer {client.config.id} with unique id {unique_id}")

    def remove_client(self, ident: Union[Client, Config, int]):
        if self.mode == MultiplexerMode.SINGLE:
            # Remove the single client
            ident = list(self.clients.values())[0].config.id

        if isinstance(ident, Client):
            client_id = ident.config.id
        elif isinstance(ident, Config):
            client_id = ident.id
        elif isinstance(ident, int):
            client_id = ident
        else:
            raise ValueError("Invalid ident type")

        client: Optional[Client] = self.get_client_by_id(client_id)

        if client is None:
            raise MultiplexerException(
                f"Cannot remove client {client_id} as it does not exist")

        if client_id in self.clients:
            del self.clients[client_id]

        for unique_id, client in self.pending_clients.items():
            if client.config.id == client_id:
                del self.pending_clients[unique_id]
                break

        if client.printer.connected:
            self.queue_event_sync(MultiplexerRemovePrinterEvent(data={
                "pid": client_id,
            }))

    def queue_event_sync(self, event: ClientEvent):
        self.event_queue.sync_q.put(event)

    def queue_update_sync(self, event: ServerEvent, for_client: Optional[int] = None):
        self.update_queue.sync_q.put((event, for_client))

    def cleanout_buffer(self):
        # Cleanout the buffer queue, in one iteration
        seek_pointer = 0
        seek_until = self.buffered_events.sync_q.qsize()
        
        while seek_pointer < seek_until:
            event, for_client = self.buffered_events.sync_q.get()

            if for_client in self.clients:
                self.logger.info(
                    f"Sending buffered event {event} with data {event.data} to client {for_client}")

                self.queue_update_sync(event, for_client)

            seek_pointer += 1
            self.buffered_events.sync_q.task_done()

    def on_add_client_response(self, event: MultiPrinterAddResponseEvent, for_client: int):
        # Clear unique_id from MultiplexerAddPrinterEvent
        if event.unique_id in MultiplexerAddPrinterEvent.unique_set:
            MultiplexerAddPrinterEvent.unique_set.remove(event.unique_id)

        # If the printer did not authenticate, remove it.
        if not event.status:
            if event.unique_id in self.pending_clients:
                del self.pending_clients[event.unique_id]

            if event.printer_id in self.clients:
                del self.clients[event.printer_id]

        elif event.unique_id in self.pending_clients:
            if not event.status:
                self.logger.info(
                    f"Removing {event.unique_id} from multiplexer as it failed to authenticate")
                self.invalid_credentials[self._format_credentials_key(
                    self.pending_clients[event.unique_id].config)] = time.time()
                del self.pending_clients[event.unique_id]
                return

            client = self.pending_clients[event.unique_id]
            client.config.id = event.printer_id
            client.printer.connected = True

            ConfigManager.persist_config(client.config)
            self.clients[client.config.id] = client
            del self.pending_clients[event.unique_id]

        self.cleanout_buffer()

    def on_setup_complete(self, event: SetupCompleteEvent, for_client: int):
        # Move printer from pending to active
        self.logger.info(f"Moving {for_client} to {event.printer_id}")
        if for_client in self.clients.keys():
            self.clients[event.printer_id] = self.clients[for_client]
            self.clients[event.printer_id].config.id = event.printer_id
            if hash(for_client) != hash(event.printer_id): del self.clients[for_client]
            ConfigManager.persist_config(self.clients[event.printer_id].config)
         
            self.queue_update_sync(event, event.printer_id)

    def on_event(self, event: ServerEvent, for_client: Optional[int] = None):
        if event is None:
            self.logger.error("Received invalid event from websocket")
            return

        if self.mode == MultiplexerMode.SINGLE:
            assert len(self.clients) + len(self.pending_clients) <= 1, "Cannot have more than one client in single mode"
            # Key is always None in single mode
            for_client = next(iter(self.clients.keys())) if len(self.clients) else next(iter(self.pending_clients.keys())) if len(self.pending_clients) else None

        if event == MultiPrinterAddResponseEvent:
            return self.on_add_client_response(event, for_client)

        if event == SetupCompleteEvent:
            self.on_setup_complete(event, for_client)
            return
        
        if not self.allow_setup and event == ConnectEvent and event.in_setup:
            # Drop connection and remove printer if we disallow setup
            self.logger.info(f"Removing {for_client} from multiplexer")
            self.remove_client(for_client)
            return

        if event == ConnectEvent and for_client in self.clients:
            # TODO, field might not be called printer
            self.clients[for_client].printer.mark_event_as_dirty(MachineDataEvent) 

        self.queue_update_sync(event, for_client)

    async def poll_events(self):
        """
        Poll events from the websocket and send them to the clients.
        """
        while True:
            if not self.is_connected():
                await self.on_disconnect(do_reconnect=True)
                continue

            try:
                await self.ws.poll_event()
            except Exception as e:
                self.logger.error(f"Error polling event:")
                self.logger.exception(e)

    async def event_consumer(self):
        while True:
            if not self.is_connected():
                await self.on_disconnect()
                continue

            event: ClientEvent = await self.event_queue.async_q.get()

            try:
                await self.ws.send_event(event)
            except Exception as e:
                self.logger.error(f"Error sending event {event.__name__}:")
                self.logger.exception(e)

            if isinstance(event, MultiplexerAddPrinterEvent):
                MultiplexerAddPrinterEvent.unique_set.remove(event.unique_id)

            self.event_queue.async_q.task_done()

    def event_producer(self):
        self.logger.info("Starting event queue producer loop")

        while True:
            for config_id in list(self.clients.keys()):
                client = self.clients.get(config_id)

                if client is None or not client.printer.connected:
                    continue

                for event in client.printer._build_events(config_id):
                    self.queue_event_sync(event)

    async def update_consumer(self):
        while True:
            event, for_client = await self.update_queue.async_q.get()

            if not for_client in self.clients:
                await self.buffered_events.async_q.put((event, for_client))
                continue

            try:
                await self.clients[for_client].handle_event(event)
            except Exception as e:
                self.logger.error(
                    f"Error handling event for {for_client} with event {event}:")
                self.logger.exception(e)

            self.update_queue.async_q.task_done()

    def ready_to_connect(self):
        return len(self.clients) + len(self.pending_clients) > 0

    def is_connected(self):
        return self.ws is not None and self.ws.is_connected()

    async def connect(self, do_reconnect=False):
        if self._connect_lock.locked():
            self.logger.info("Already connecting to websocket")

            # Await lock to be released then check if we are connectedwwwwwwwwwwww
            await self._connect_lock.acquire()

            if self.ws.is_connected():
                self._connect_lock.release()
                return

        try:
            async with self._connect_lock:
                if not self.ready_to_connect():
                    return

                self.logger.info(f"Connecting to {self.url}")

                if self.ws is None:
                    self.ws = await SimplyPrintWebSocket.from_url(
                        url=self.url,
                        on_event=self.on_event,
                        on_disconnect=self.on_disconnect,
                        do_reconnect=self.ready_to_connect,
                        loop=asyncio.get_running_loop(),
                        timeout=self.connect_timeout)
                else:
                    await self.ws.connect()

                if do_reconnect:
                    await self.on_reconnect()

                self.logger.info("Connected to websocket")

        except (aiohttp.WSServerHandshakeError, aiohttp.ClientConnectorError):
            self.logger.error(
                f"Failed to connect to websocket at {self.url} retrying in {self.connect_timeout} seconds")

            await asyncio.sleep(self.connect_timeout)
            await self.connect()

        finally:
            if self._connect_lock.locked():
                self._connect_lock.release()

    async def on_reconnect(self):
        await self._reconnect_lock.acquire()

        self.logger.info("Was not connected to websocket, reading clients...")


        try:
            if not self.ready_to_connect() or not self.is_connected():
                self.logger.info(
                    f"No clients to reconnect, or not connceted. Skipping for {self.connect_timeout} seconds waiting for clients")

                await asyncio.sleep(self.connect_timeout)
                return

            # Mark all clients as disconnected
            for client in list(self.clients.values()) + list(self.pending_clients.values()):
                client.printer.connected = False

            if self.mode == MultiplexerMode.SINGLE:
                self.get_single_client().printer.connected = True
                return

            # Move all non connected clients to pending
            # and readd them to the multiplexer connection
            for client in list(self.clients.values()):
                if not client.printer.connected:
                    self.pending_clients[client.config.unique_id] = client
                    del self.clients[client.config.id]


            for unique_id in list(self.pending_clients.keys()):
                config = self.pending_clients[unique_id].config

                # Mark printer info as changed
                # TODO, field might not be called printer
                self.pending_clients[unique_id].printer.mark_event_as_dirty(MachineDataEvent) 
                
                try:
                    self.queue_event_sync(MultiplexerAddPrinterEvent(
                        config, allow_setup=self.allow_setup))
                except MultiplexerException:
                    pass  # Already in the queue
        finally:
            self._reconnect_lock.release()

    async def on_disconnect(self, do_reconnect=False):
        await self._disconnect_lock.acquire()
        try:
            if not self.ready_to_connect():
                self.logger.info(
                    f"No clients to connect, retrying in {self.connect_timeout} seconds")

                await asyncio.sleep(self.connect_timeout)
                return

            await self.connect(do_reconnect)
        finally:
            self._disconnect_lock.release()

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None, consumer_count: int = 1):
        """
        Do connection and read/write loops.
        """

        if self.sentry.sentry_dsn is not None:
            self.sentry.initialize_sentry()

        async def wrapped_start():
            self.buffered_events = janus.Queue()
            self.update_queue = janus.Queue()
            self.event_queue = janus.Queue()

            await self.connect(do_reconnect=True)

            await asyncio.gather(*[
                asyncio.create_task(self.poll_events()),
                *[asyncio.create_task(self.update_consumer()) for _ in range(consumer_count)],
                *[asyncio.create_task(self.event_consumer()) for _ in range(consumer_count)]
            ])

        self.loop = loop or asyncio.new_event_loop()
        self.loop.run_in_executor(None, self.event_producer)
        self.loop.run_until_complete(wrapped_start())
        self.loop.run_forever()

    def stop(self):
        """
        Stops the multiplexer event loop and thread.
        """
        async def wrapped_stop():
            if self.is_connected():
                await self.ws.close()

        self.loop.stop()
        self.loop.run_until_complete(wrapped_stop())
        self.loop.close()
