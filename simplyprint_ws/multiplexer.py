from enum import Enum
import time
import json
import logging
import asyncio
import threading

from tornado import httpclient
from tornado.websocket import WebSocketClientConnection, websocket_connect

from .events import ClientEvent, ServerEvent, parse_event_dict, get_event, events
from .config import Config
from .const import WEBSOCKET_URL, API_VERSION
from .client.client import Client

from abc import abstractmethod
from typing import Any,Dict, Optional, Tuple

class MultiplexerAddPrinterEvent(ClientEvent):
    event_type = "add_connection"

class MultiplexerRemovePrinterEvent(ClientEvent):
    event_type = "remove_connection"

class MultiplexerMode(Enum):
    MULTIPRINTER = "mp"
    SINGLE = "p"

class Multiplexer:
    """

    """
    
    url: str
    mode: MultiplexerMode = MultiplexerMode.SINGLE
    connect_timeout: Optional[float]

    websocket: Optional[WebSocketClientConnection] = None
    clients: Dict[Config, Client] = {}

    write_queue = asyncio.Queue(maxsize=10000000)

    event_producer_loop: Optional[asyncio.Task] = None
    write_consumer_loop: Optional[asyncio.Task] = None
    write_producer_loop: Optional[asyncio.Task] = None

    client_tasks = []

    logger: logging.Logger = logging.getLogger("multiplexer")

    def __init__(self, mode: MultiplexerMode, single_config: Optional[Config] = None, connect_timeout: Optional[float] = None):
        self.mode = mode
        self.connect_timeout = connect_timeout or 1

        self.url = self.get_url(single_config)

    def get_url(self, config: Optional[Config] = None):
        return f"{WEBSOCKET_URL}/{API_VERSION}/{self.mode.value}" + (f"/{config.id}/{config.token}" if config.id is not None and config.id != 0 else "/0/0")

    async def connect(self):
        if self.websocket is not None:
            self.logger.warn("Already connected to websocket")
            return

        self.websocket = await websocket_connect(self.url, connect_timeout=self.connect_timeout)

        if self.websocket is None:
            self.logger.critical("Failed to connect to websocket")
            raise Exception("Failed to connect to websocket")
        
        self.logger.info(f"Connected to websocket {self.url}")
        
    async def reconnect(self):
        self.logger.info("Attempting to reconnect to websocket")
        while self.websocket is None:
            try:
                await self.connect()
            except Exception as e:
                self.logger.error("Failed to connect to websocket with error: " + str(e) + ". Retrying in 1 second")
                await asyncio.sleep(1)
        
        self.logger.info("Reconnected to websocket")

    async def on_disconnect(self):
        self.logger.warn(f"Websocket disconnected with code {self.websocket.close_code if self.websocket else None} and reason {self.websocket.close_reason if self.websocket else None}")
        
        for client in self.clients.values():
            client.is_connected = False

        if self.websocket is not None:
            self.websocket.close()
            self.websocket = None

        await self.reconnect()

    def add_client(self, config: Config, client: Client):
        def send_handle(event: ClientEvent):
            self.client_send_handle(event, config)

        client.send_event = send_handle

        self.clients[config] = client

        if self.websocket is None:
            # If the websocket is already closed, we can't connect
            self.clients[config].is_connected = False
            return

    def remove_client(self, config: Config):
        if not config in self.clients:
            return
        
        if self.clients[config].is_connected:
            # TODO disconnect from websocket
            pass

        del self.clients[config]

    
    def client_send_handle(self, event: ClientEvent, config: Config):
        try:
            self.write_queue.put_nowait((event, config))
        except asyncio.QueueFull:
            self.logger.error("Write queue full")
            return
        
    async def client_tasks_loop(self):
        while True:
            popped_tasks = self.client_tasks.copy()
            self.client_tasks.clear()
            await asyncio.gather(*popped_tasks)

    async def send_item(self, item: Tuple[ClientEvent, Config]):
        event, config = item
        message = event.generate()

        if self.mode == MultiplexerMode.MULTIPRINTER:
            message["for"] = config.id

        try:
            await self.websocket.write_message(json.dumps(message))
        except Exception:
            self.logger.error("Failed to write to websocket")
            await self.on_disconnect()

    async def write_queue_consumer(self):
        """
        This loop is responsible for writing to the websocket 
        from the write queue and sending it to the server
        """
        self.logger.info("Starting write queue consumer loop")

        while True:
            if self.websocket is None:
                continue

            try:
                item: Tuple[ClientEvent, Config] = await self.write_queue.get()
            except asyncio.QueueEmpty:
                continue

            await self.send_item(item)
            self.write_queue.task_done()

    async def write_queue_producer(self):
        """ 
        Compile dirty state into events from clients and put into write queue
        """
        self.logger.info("Starting write queue producer loop")

        while True:
            for config, client in self.clients.items():
                if not client.is_connected:
                    continue
                    
                for event in client.printer._build_events():
                    await self.write_queue.put((event, config))

    async def event_queue_producer(self):
        self.logger.info("Starting event queue producer loop")

        while True:
            if self.websocket is None:
                await self.on_disconnect()

            message = await self.websocket.read_message()

            if message is None:
                await self.on_disconnect()
                continue
            
            if message is bytes:
                self.logger.error("Received bytes from websocket")
                continue
            
            try:
                event: Dict[str, Any] = json.loads(message)
            except json.JSONDecodeError:
                self.logger.error("Received invalid JSON from websocket")
                continue
            
            event: Optional[ServerEvent] = parse_event_dict(event)

            if self.mode == MultiplexerMode.SINGLE:
                assert len(self.clients) == 1
                client = list(self.clients.values())[0]
                self.client_tasks.append(client.handle_event(event))
                continue

            forClient: Optional[int] = event.pop("for", None)

            if event is None:
                self.logger.error("Received invalid event from websocket")
                continue

            if not forClient in self.clients:
                self.logger.error(f"Received event for unknown client {forClient}")
                continue

            self.client_tasks.append(self.clients[forClient].handle_event(event))

    async def start(self):
        """
        Do connection and read/write loops.
        """
        await self.reconnect()
        
        self.write_consumer_loop = asyncio.create_task(self.write_queue_consumer())
        self.event_producer_loop = asyncio.create_task(self.event_queue_producer())
        self.write_producer_loop = asyncio.create_task(self.write_queue_producer())

        self.client_thread = threading.Thread(target=asyncio.run, args=(self.client_tasks_loop(),), daemon=True)
        self.client_thread.start()

        # run the loops concurrently
        await asyncio.gather(self.event_producer_loop, self.write_producer_loop, self.write_consumer_loop)

    def stop(self):
        """
        Stop the multiplexer.
        """
        if self.websocket is not None:
            self.websocket.close()

        if self.event_producer_loop is not None:
            self.event_producer_loop.cancel()
            self.event_producer_loop = None
        
        if self.write_producer_loop is not None:
            self.write_producer_loop.cancel()
            self.write_producer_loop = None

        if self.write_consumer_loop is not None:
            self.write_consumer_loop.cancel()
            self.write_consumer_loop = None

        if self.client_thread is not None:
            self.client_thread.join()
            self.client_thread = None

