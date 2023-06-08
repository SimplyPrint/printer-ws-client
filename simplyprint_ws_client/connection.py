import json
import requests

from tornado.websocket import WebSocketClientConnection, WebSocketClosedError, websocket_connect
from logging import Logger

from .const import REACHABLE_URL, WEBSOCKET_URL

from .event import events, Event

from typing import (
    Optional,
    Dict,
    Any,
    Union,
)


class Connection:
    def __init__(self, logger: Logger) -> None:
        self.ws: Optional[WebSocketClientConnection] = None

        self.api_version: str = "0.1"
        self.reconnect_token: Optional[str] = None

        self.log_connect: bool = True
        self.logger: Logger = logger

    def is_connected(self) -> bool:
        return self.ws is not None

    def get_url(self, id: str, token: str) -> str:
        return f"{WEBSOCKET_URL}/{self.api_version}/p/{id}/{token}"

    async def connect(self, id: str, token: str) -> None:
        url = self.get_url(id, token)

        if self.reconnect_token is not None:
            url = f"{url}/{self.reconnect_token}"

        if self.log_connect:
            self.logger.info(f"Connecting to {url}")

        try:
            requests.get(REACHABLE_URL, timeout=5.0)
        except Exception:
            return

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
            fut = self.ws.write_message(message)
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

        name: str = packet.get("type", "")
        demand = packet.get("demand", "")
        data: Dict[str, Any] = packet.get("data", {})

        event: Union[Event, Dict[str, Event]] = events.get(name, None)

        if isinstance(event, dict) and event is not None:
            event: Event = event.get(demand, None)

        if event is None:
            self.logger.debug(f"Invalid event '{name}' or demand '{demand}'")
            return None

        return event(name=name, demand=demand, data=data)
