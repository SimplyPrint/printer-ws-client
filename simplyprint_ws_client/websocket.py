import asyncio
import json
import logging
import threading
from typing import Any, Awaitable, Callable, Dict, Optional
try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

import aiohttp

from .events import get_event
from .events.client_events import ClientEvent, ClientEventMode
from .events.events import ServerEvent


class SimplyPrintWebSocket:

    loop: asyncio.AbstractEventLoop
    session: aiohttp.ClientSession
    socket: aiohttp.ClientWebSocketResponse

    url: str

    _on_event: Callable[[ServerEvent, Optional[int]], None]
    _on_disconnect: Callable[[], Awaitable[None]]
    _do_reconnect: Callable[[], bool]

    timeout: float = 5.0

    thread_id: int
    logger: logging.Logger = logging.getLogger("websocket")

    def __init__(self, socket: aiohttp.ClientWebSocketResponse, loop: asyncio.AbstractEventLoop) -> None:
        self.socket = socket
        self.loop = loop
        self.thread_id = threading.get_ident()

    @classmethod
    async def from_url(
        cls,
        url: str,
        on_event: Callable[[ServerEvent, Optional[int]], None],
        on_disconnect: Callable[[], Awaitable[None]],
        do_reconnect: Callable[[], bool],
        loop: asyncio.AbstractEventLoop,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: Optional[float] = None
    ) -> Self:
        """

        """
        timeout = timeout or cls.timeout
        session = session or aiohttp.ClientSession(loop=loop)
        socket = await session.ws_connect(url, timeout=timeout, autoclose=False, max_msg_size=0, compress=False)

        ws = cls(socket, loop)
        ws.session = session
        ws.timeout = timeout
        ws.url = url
        ws._on_event = on_event
        ws._on_disconnect = on_disconnect or ws.on_disconnect
        ws._do_reconnect = do_reconnect

        return ws

    async def connect(self) -> None:
        """
        Primarely used for reconnection
        """
        if not self.session:
            raise RuntimeError("Cannot connect without a session")

        if self.is_connected():
            return

        await self.socket.close()
        self.socket = await self.session.ws_connect(self.url, timeout=self.timeout, autoclose=False, max_msg_size=0, compress=False)

    async def close(self) -> None:
        await self.socket.close()
        await self.session.close()

    async def recieved_message(self, message: str):
        try:
            event: Dict[str, Any] = json.loads(message)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse event: {message}")
            return

        name: str = event.get("type", "")
        data: Dict[str, Any] = event.get("data", {})
        for_client: Optional[int] = event.get("for")
        demand: Optional[str] = data.get("demand")

        try:
            event: ServerEvent = get_event(name, demand, data)
        except KeyError as e:
            self.logger.error(f"Unknown event type {e.args[0]}")
            return

        self.logger.debug(
            f"Recieved event {event} with data {data} for client {for_client}")

        self.on_event(event, for_client)

    async def poll_event(self) -> None:
        if not self.is_connected():
            await self.on_disconnect()

        try:
            message = await self.socket.receive()

            if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSE):
                return

            if message.type == aiohttp.WSMsgType.ERROR:
                self.logger.error(f"Websocket error: {str(message.data)}")
                return

            if message.type == aiohttp.WSMsgType.BINARY:
                message.data = message.data.decode("utf-8")

            await self.recieved_message(message.data)

        except (asyncio.CancelledError, asyncio.TimeoutError):
            await self.on_disconnect()

    async def send_event(self, event: ClientEvent) -> None:
        if not self.is_connected():
            await self.on_disconnect()

        try:
            message = event.as_dict()

            if (mode := event.on_send()) == ClientEventMode.DISPATCH:
                await self.socket.send_json(message)
                self.logger.debug(f"Sent event {event} with data {message}")
            else:
                self.logger.debug(
                    f"Did not send event {event} with data {message} because of mode {mode.name}")

        except ConnectionResetError as e:
            self.logger.error(f"Failed to send event {event}: {e}")
            await self.on_disconnect()

    def is_connected(self) -> bool:
        return self.socket is not None and not self.socket.closed

    def on_event(self, event: ServerEvent, for_client: Optional[int]) -> None:
        self._on_event(event, for_client)

    async def on_disconnect(self) -> None:
        if hasattr(self, "_on_disconnect"):
            await self._on_disconnect()

        if hasattr(self, "_do_reconnect") and self._do_reconnect():
            await self.connect()
