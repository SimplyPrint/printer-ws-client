import logging
import asyncio
import threading

from enum import Enum
from typing import Dict, List, Optional

from .websocket import SimplyPrintWebSocket
from .events import ClientEvent, ServerEvent
from .config import Config
from .const import WEBSOCKET_URL, API_VERSION
from .client.client import Client

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

    ws: Optional[SimplyPrintWebSocket] = None
    clients: Dict[Config, Client] = {}

    tasks_handles = []
    tasks_updates = []
    threads: List[threading.Thread] = []

    logger: logging.Logger = logging.getLogger("multiplexer")

    def __init__(self, mode: MultiplexerMode, single_config: Optional[Config] = None, connect_timeout: Optional[float] = None):
        self.mode = mode
        self.connect_timeout = connect_timeout or 1

        self.url = self.get_url(single_config)

    def get_url(self, config: Optional[Config] = None):
        return f"{WEBSOCKET_URL}/{API_VERSION}/{self.mode.value}" + (f"/{config.id}/{config.token}" if config.id is not None and config.id != 0 else "/0/0")


    def add_client(self, config: Config, client: Client):
        def send_handle(event: ClientEvent):
            self.client_send_handle(event, config)

        client.send_event = send_handle

        self.clients[config] = client

        if self.ws is None:
            # If the websocket is already closed, we can't connect
            self.clients[config].printer.connected = False
            return

    def remove_client(self, config: Config):
        if not config in self.clients:
            return
        
        if self.clients[config].printer.connected:
            # TODO disconnect from websocket
            pass

        del self.clients[config]

    
    def client_send_handle(self, event: ClientEvent, config: Config):
        event.forClient = config.id
        self.tasks_handles.append(self.ws.send_event(event))

    def on_event(self, event: ServerEvent):
        if self.mode == MultiplexerMode.SINGLE:
            assert len(self.clients) == 1
            client = list(self.clients.values())[0]
            self.tasks_handles.append(client.handle_event(event))
            return

        forClient: Optional[int] = event.pop("for")

        if event is None:
            self.logger.error("Received invalid event from websocket")
            return

        if not forClient in self.clients:
            self.logger.error(f"Received event for unknown client {forClient}")
            return

        self.tasks_handles.append(self.clients[forClient].handle_event(event))

    async def poll_events(self):
        """
        Poll events from the websocket and send them to the clients.
        """
        while True:
            await self.ws.poll_event()

    async def task_consumer_handles(self):
        while True:
            popped_tasks = self.tasks_handles.copy()
            await asyncio.gather(*popped_tasks)

            for task in popped_tasks:
                self.tasks_handles.remove(task)
    
    async def task_consumer_updates(self):
        while True:
            popped_tasks = self.tasks_updates.copy()
            await asyncio.gather(*popped_tasks)

            for task in popped_tasks:
                self.tasks_updates.remove(task)

    def task_producer(self):
        self.logger.info("Starting event queue producer loop")

        while True:
            for config, client in self.clients.items():
                if not client.printer.connected:
                    continue
                    
                for event in client.printer._build_events(config.id):
                    self.tasks_updates.append(self.ws.send_event(event))

    async def start(self):
        """
        Do connection and read/write loops.
        """
        self.ws = await SimplyPrintWebSocket.from_url(self.url, self.on_event, asyncio.get_running_loop(), self.connect_timeout)

        self.threads.append(threading.Thread(target=asyncio.run, args=(self.task_consumer_updates(),), daemon=True))
        self.threads.append(threading.Thread(target=asyncio.run, args=(self.task_consumer_handles(),), daemon=True))
        self.threads.append(threading.Thread(target=self.task_producer, daemon=True))

        for thread in self.threads:
            thread.start()

        # run the loops concurrently
        await self.poll_events()

    async def stop(self):
        """
        Stop the multiplexer.
        """
        if self.ws is not None:
            await self.ws.close()

        for thread in self.threads:
            thread.join()

