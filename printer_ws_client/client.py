import asyncio
import threading
import logging
import json

from .printer_state import PrinterState
from .connection import Connection
from .event import *

from logging import Logger
from typing import Callable

class Client:
    def __init__(self):
        self.simplyprint_thread = threading.Thread(
            target=self._run_simplyprint_thread, 
            daemon=True,
        )

        self.logger: Logger = logging.getLogger("simplyprint.client")

        self.should_close: bool = False
        self.callbacks: EventCallbacks = EventCallbacks()

        # connection
        self.connection: Connection = Connection(self.logger)
        
        # printer state
        self.state: PrinterState = PrinterState()
        

    def _run_simplyprint_thread(self) -> None:
        self._aioloop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._aioloop)
        self._aioloop.run_until_complete(self.process_events())

    def on_new_token(self, callback: Callable[[NewTokenEvent], None]) -> None:
        self.callbacks.on_new_token = callback

    def on_connect(self, callback: Callable[[ConnectEvent], None]) -> None:
        self.callbacks.on_connect = callback

    def on_pause(self, callback: Callable[[PauseEvent], None]) -> None:
        self.callbacks.on_pause = callback 

    def set_id(self, id: str) -> None:
        self.connection.id = id

    def set_token(self, token: str) -> None:
        self.connection.token = token

    def start(self) -> None:
        if self.simplyprint_thread.is_alive():
            return
        self.simplyprint_thread.start()

    def set_layer(self, layer: int) -> None:
        self.state.layer = layer

    def send_json(self, data: Any) -> None:
        message = json.dumps(data)
        self.send_message(message)

    def send_message(self, message: str) -> None:
        asyncio.run_coroutine_threadsafe(
            self.send_message_async(message), 
            self._aioloop
        )

    async def send_message_async(self, message: str) -> None:
        while True:
            if not self.connection.is_connected():
                await self.connection.connect()
                continue

            print(f"sending message{message}") 
            await self.connection.send_message(message)
            break

    async def process_events(self):
        while not self.should_close:
            while not self.connection.is_connected():
                await self.connection.connect()

            event = await self.connection.read_event()

            if event is None:
                continue

            if isinstance(event, NewTokenEvent):
                self.handle_new_token_event(event)
            elif isinstance(event, ConnectEvent):
                self.handle_connect_event(event)
            elif isinstance(event, PauseEvent):
                self.handle_pause_event(event)
            
    def handle_new_token_event(self, event: NewTokenEvent) -> None:
        self.connection.token = event.token
        self.callbacks.on_new_token(event)

    def handle_connect_event(self, event: ConnectEvent) -> None:
        self.connection.reconnect_token = None
        self.callbacks.on_connect(event)

    def handle_pause_event(self, event: PauseEvent) -> None:
        self.callbacks.on_pause(event)
