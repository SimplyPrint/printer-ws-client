import asyncio
import logging
from enum import Enum
from typing import Coroutine, Dict, List, Optional, Tuple, Union

import aiohttp
import janus

from .client import Client
from .config import Config, ConfigManager
from .const import API_VERSION, WEBSOCKET_URL
from .events import ClientEvent, ServerEvent
from .events.events import (ConnectEvent, MultiPrinterAddResponseEvent,
                            SetupCompleteEvent)
from .helpers.sentry import Sentry
from .websocket import SimplyPrintWebSocket


class MultiplexerException(RuntimeError):
    pass

class MultiplexerClientEvents(Enum):
    ADD_PRINTER = "add_connection"
    REMOVE_PRINTER = "remove_connection"

class MultiplexerAddPrinterEvent(ClientEvent):
    event_type = MultiplexerClientEvents.ADD_PRINTER

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

    url: str
    mode: MultiplexerMode = MultiplexerMode.SINGLE
    connect_timeout: Optional[float]

    ws: Optional[SimplyPrintWebSocket] = None
    clients: Dict[int, Client] = {}
    pending_clients: Dict[str, Client] = {}
    allow_setup: bool = False
    
    buffered_events: List[Tuple[ServerEvent, Optional[int]]] = []
    task_queue: janus.Queue

    sentry: Sentry = Sentry()
    logger: logging.Logger = logging.getLogger("multiplexer")
    _connect_lock = asyncio.Lock()
    _disconnect_lock = asyncio.Lock()

    def __init__(self, mode: MultiplexerMode, single_config: Optional[Config] = None, connect_timeout: Optional[float] = None):        
        self.mode = mode
        self.connect_timeout = connect_timeout or 1

        self.url = self.get_url(single_config)

    def get_url(self, config: Optional[Config] = None):
        return f"{WEBSOCKET_URL}/{API_VERSION}/{self.mode.value}" + (f"/{config.id}/{config.token}" if config is not None and config.id is not None and config.id != 0 else "/0/0")

    def get_client_by_id(self, client_id: int):
        if client_id in self.clients:
            return self.clients.get(client_id)
        
        # Linear search for client in pending clients
        for client in self.pending_clients.values():
            if client.config.id == client_id:
                return client
        
        return None
    
    def get_clients_by_token(self, token: str):
        return [client for client in self.clients.values() if client.config.token == token] + [client for _, client in self.pending_clients.values() if client.config.token == token]

    def add_client(self, client: Client, unique_id: Optional[str] = None, public_ip: Optional[str] = None):
        if self.ws is None or not self.ws.is_connected():
            raise MultiplexerException("Cannot add client without being connected")

        client.sentry = self.sentry
        client.send_event = lambda event: self.client_send_handle(event, client.config)
        client.printer.connected = True

        if self.mode == MultiplexerMode.SINGLE:
            assert len(self.clients) == 0
            self.clients[client.config.id] = client
            return
        
        client.printer.connected = False

        if unique_id is None:
            unique_id = str(id(client))

        self.pending_clients[unique_id] = client

        self.task_queue.sync_q.put(self.ws.send_event(MultiplexerAddPrinterEvent(data={
            "pid": client.config.id,
            "token": client.config.token,
            "unique_id": unique_id,
            "allow_setup": self.allow_setup,
            "public_ip": public_ip,
        })))
        
        self.logger.debug(f"Added printer {client.config.id} with unique id {unique_id}")

    def remove_client(self, ident: Union[Client, Config, int]):
        if self.ws is None:
            raise MultiplexerException("Cannot add client without being connected")
        
        if isinstance(ident, Client): client_id = ident.config.id
        elif isinstance(ident, Config): client_id = ident.id
        else: client_id = ident

        client: Optional[Client] = self.get_client_by_id(client_id)

        if client is None:
            raise MultiplexerException(f"Cannot remove client {client_id} as it does not exist")

        if client_id in self.clients:
            del self.clients[client_id]
        
        for unique_id, client in self.pending_clients.items():
            if client.config.id == client_id:
                del self.pending_clients[unique_id]
                break
        
        if client.printer.connected:
            self.task_queue.sync_q.put(self.ws.send_event(MultiplexerRemovePrinterEvent(data={
                "pid": client_id,
            })))
    
    async def client_send_handle(self, event: ClientEvent, config: Config):
        event.forClient = config.id
        self.task_queue.sync_q.put(self.ws.send_event(event))

    def on_event(self, event: ServerEvent, forClient: Optional[int] = None):
        if self.mode == MultiplexerMode.SINGLE:
            assert len(self.clients) == 1
            client = list(self.clients.values())[0]
            self.task_queue.sync_q.put(client.handle_event(event))
            return
 
        if event == MultiPrinterAddResponseEvent:
            # If the printer did not authenticate, remove it.
            if not event.status:
                if event.unique_id in self.pending_clients: del self.pending_clients[event.unique_id]
                if event.printer_id in self.clients: del self.clients[event.printer_id]
            elif event.unique_id in self.pending_clients.keys():
                if not event.status:
                    self.logger.info(f"Removing {event.unique_id} from multiplexer as it failed to authenticate")
                    del self.pending_clients[event.unique_id]
                    return

                client = self.pending_clients[event.unique_id]
                client.config.id = event.printer_id
                ConfigManager.persist_config(client.config)
                client.printer.connected = True
                self.clients[client.config.id] = client
                del self.pending_clients[event.unique_id]
            
            self.cleanout_buffer()
            return

        if event == SetupCompleteEvent:
            # Move printer from pending to active
            self.logger.info(f"Moving {forClient} to {event.printer_id}")
            if forClient in self.clients.keys():
                self.clients[event.printer_id] = self.clients[forClient]
                del self.clients[forClient]

        if event == ConnectEvent and not self.allow_setup and event.in_setup:
            # Drop connection and remove printer
            self.logger.info(f"Removing {forClient} from multiplexer")
            self.remove_client(forClient)
            return

        if event is None:
            self.logger.error("Received invalid event from websocket")
            return

        if not forClient in self.clients:
            self.logger.error(f"Received event for unknown client {forClient}")
            self.buffered_events.append((event, forClient))
            return

        self.task_queue.sync_q.put(self.clients[forClient].handle_event(event))

    async def on_disconnect(self):
        if self._disconnect_lock.locked():
            self.logger.info("Already captured disconnect from websocket to reconnect later")
            return

        self.logger.info("Captured disconnect from websocket, reconnecting")

        async with self._disconnect_lock:
            # Pop all pending clients and clients
            clients: List[Client] = list(self.clients.values()) + list(self.pending_clients.values())
            
            self.clients.clear()
            self.pending_clients.clear()

            # Mark all clients as disconnected
            for client in clients:
                client.printer.connected = False

            await self.connect()

            # Once connected, re-add all clients
            for client in clients:
                self.add_client(client)


    def cleanout_buffer(self):
        # Cleanout the buffer queue, in one iteration
        for event, forClient in self.buffered_events:
            if forClient in self.clients:
                self.logger.info(f"Sending buffered event {event} with data {event.data} to client {forClient}")
                self.task_queue.sync_q.put(self.clients[forClient].handle_event(event))

    async def poll_events(self):
        """
        Poll events from the websocket and send them to the clients.
        """
        while True:
            try:
                await self.ws.poll_event()
            except Exception as e:
                self.logger.error(f"Error polling event: {e}")

                if not self.ws.is_connected():
                    await self.on_disconnect()

    async def task_consumer(self):
        while True:
            task: Coroutine = await self.task_queue.async_q.get()

            try:
                await task
            except Exception as e:
                self.logger.error(f"Error running task {task.__name__}: {e}")

            self.task_queue.async_q.task_done()

    def task_producer(self):
        self.logger.info("Starting event queue producer loop")        
        while True:
            for config_id in list(self.clients.keys()):
                client = self.clients.get(config_id)

                if client is None or not client.printer.connected:
                    continue
                    
                for event in client.printer._build_events(config_id):
                    self.task_queue.sync_q.put(self.ws.send_event(event))
    
    async def connect(self):
            if self._connect_lock.locked():
                self.logger.info("Already connecting to websocket")

                # Await lock to be released then check if we are connected
                await self._connect_lock.acquire()

                if self.ws.is_connected():
                    self._connect_lock.release()
                    return

            try:
                async with self._connect_lock:
                    self.logger.info(f"Connecting to {self.url}")

                    self.ws = await SimplyPrintWebSocket.from_url(
                        url=self.url,
                        on_event=self.on_event,
                        on_disconnect=self.on_disconnect,
                        loop=asyncio.get_running_loop(),
                        session=self.ws.session if self.ws is not None else None,
                        timeout=self.connect_timeout)
                    
                    self.logger.info("Connected to websocket")

            except (aiohttp.WSServerHandshakeError, aiohttp.ClientConnectorError):
                self.logger.error(f"Failed to connect to websocket at {self.url} retrying in {self.connect_timeout or 1} seconds")
                await asyncio.sleep(self.connect_timeout or 1)
                await self.connect()

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None, consumer_count: int = 1):
        """
        Do connection and read/write loops.
        """

        if self.sentry.sentry_dsn is not None:
            self.sentry.initialize_sentry()

        async def wrapped_start():
            self.task_queue = janus.Queue()
            await self.connect()

            await asyncio.gather(*[
                asyncio.create_task(self.poll_events()),
                *[asyncio.create_task(self.task_consumer()) for _ in range(consumer_count)]
            ])

        self.loop = loop or asyncio.new_event_loop()
        self.loop.run_in_executor(None, self.task_producer)
        self.loop.run_until_complete(wrapped_start())
        self.loop.run_forever()

    def stop(self):
        """
        Stops the multiplexer event loop and thread.
        """
        async def wrapped_stop():
            if self.ws is not None: await self.ws.close()

        self.loop.stop()
        self.loop.run_until_complete(wrapped_stop())
        self.loop.close()
