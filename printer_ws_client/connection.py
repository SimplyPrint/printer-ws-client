import json

from tornado.websocket import WebSocketClientConnection, WebSocketClosedError, websocket_connect
from logging import Logger

from .event import *

from typing import (
    Optional, 
    Dict, 
    Any, 
)

class Connection:
    def __init__(self, logger: Logger) -> None:
        self.ws: Optional[WebSocketClientConnection] = None

        self.api_version: str = "0.1"
        self.id: Optional[str] = None
        self.token: Optional[str] = None
        self.reconnect_token: Optional[str] = None

        self.log_connect: bool = True
        self.logger: Logger = logger

    def is_connected(self) -> bool:
        return self.ws is not None

    def get_url(self) -> str:
        if self.id is None or self.token is None:
            return f"wss://testws.simplyprint.io/{self.api_version}/p/0/0"

        return f"wss://testws.simplyprint.io/{self.api_version}/p/{self.id}/{self.token}"

    async def connect(self) -> None:
        url = self.get_url()

        if self.reconnect_token is not None:
            url += f"{url}/{self.reconnect_token}"

        if self.log_connect:
            self.logger.info(f"Connecting to {url}")

        self.ws = await websocket_connect(url, connect_timeout=5.0)

    def _log_disconnect(self) -> None:
        if self.ws is None:
            return

        reason = self.ws.close_reason
        code = self.ws.close_code

        msg = (
            f"SimplyPrint Disconnected - Code: {code} Reason: {reason}"
        ) 

        self.logger.info(msg)

    async def send_message(self, message: str) -> None:
        if self.ws is None:
            raise Exception("not connected")

        try:
            fut = self.ws.write_message(message);
        except WebSocketClosedError:
            self._log_disconnect()

            self.ws = None
            return

        await fut

    
    async def read_message(self) -> Optional[str]:
        if self.ws is None:
            raise Exception("not connected")

        message = await self.ws.read_message()

        if message is None: 
            self._log_disconnect()

            # remove websocket
            self.ws = None
            return None

        if message is bytes:
            raise Exception("message is bytes, expected str")

        return str(message)

    async def read_event(self) -> Optional[Event]:
        message = await self.read_message()

        if message is None:
            return None

        try:
            packet: Dict[str, Any] = json.loads(message)
        except json.JSONDecodeError:
            self.logger.debug(f"Invalid message, not JSON: {message}")
            return None

        event: str = packet.get("type", "")
        data: Dict[str, Any] = packet.get("data", {})

        if event == "new_token":
            return NewTokenEvent(data)
        elif event == "connected":
            return ConnectEvent(data)
        elif event == "pause":
            return PauseEvent()
        else:
            self.logger.debug(f"Unknown event: {event} data: {data}")
            return None
