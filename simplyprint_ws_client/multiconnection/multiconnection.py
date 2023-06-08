from asyncio import Future
import asyncio
import json
import logging
import threading
from typing import Dict, List, Optional, Union

from ..client_old.async_loop import AsyncThread
from .fake_ws import FakeWS
from .connection import ProxiedConnection, ProxiedClient
from tornado.websocket import WebSocketClientConnection, WebSocketClosedError, websocket_connect

from ..const import WEBSOCKET_URL


class MultiConnection:
    ws: Optional[WebSocketClientConnection] = None
    connections: List[ProxiedClient]

    def __init__(self):
        self.api_version: str = "0.1"
        self.connections = []

    def start(self):
        # Spawn two tasks, one for reading from the websocket and one for writing to it
        # asyncio.create_task(self.write_to_ws())
        # Instead run in new thread
        self.write_to_ws_t = AsyncThread(self.write_to_ws())
        self.write_to_ws_t.start()

    async def connect(self):
        if self.is_connected():
            return

        self.ws = await websocket_connect(self.get_url(), callback=self.on_future_done, connect_timeout=5.0, on_message_callback=self.on_message)

    def is_connected(self) -> bool:
        return self.ws is not None

    def get_url(self) -> str:
        return f"{WEBSOCKET_URL}/{self.api_version}/mp/te/he"
    
    def message_as_json(self, message: Union[str, bytes]):
        # Ensure message is a string and json
        try:
            if isinstance(message, dict): return message
            if isinstance(message, bytes): message = message.decode()
            return json.loads(message)
        except json.JSONDecodeError:
            raise ValueError("Message is not valid json")
        
    async def send_message(self, message: str) -> None:
        print(f"Sending message (executed): {message}")

        try:
            fut = self.ws.write_message(message)
        except WebSocketClosedError:
            self.ws = None
            print("Connection closed")
            
    async def add_connection(self, connection: ProxiedClient):
        self.connections.append(connection)

        await self.send_message(json.dumps({
            "type": "add_connection",
            "data": {
                "pid": connection.config.id,
                "token": connection.config.token,
            }
        }))

    async def remove_connection(self, connection: ProxiedClient):
        self.connections.remove(connection)

        await self.ws.send_message(json.dumps({
            "type": "remove_connection",
            "data": {
                "pid": connection.config.id,
            }
        }))

    def on_message(self, message: Union[str, bytes]):
        if message is None:
            # WS closed
            return

        message = self.message_as_json(message)

        if "for" in message and message["for"] in FakeWS._read_queues:
            pid = message["for"]
            del message["for"]
            FakeWS.send_message_to(pid, json.dumps(message))
        else:
            print(f"Received message: {message}")

    def on_future_done(self, future):
        print(f"Future done: {future}")

    async def read_from_ws(self):
        while self.ws is not None:
            await self.ws.read_message()

    async def write_to_ws(self):
        while self.ws is not None:
            for [pid, message] in FakeWS.dump_write_queue():
                print(f"Sending message (queued): {message} to {pid}")
                message = self.message_as_json(message)
                message["for"] = pid
                message = json.dumps(message)
                await self.send_message(message)