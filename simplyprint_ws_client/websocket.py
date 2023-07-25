from abc import abstractmethod
import json
import aiohttp
import asyncio
import logging
import threading

from typing import Any, Awaitable, Callable, Optional, Self, Dict

from .events import get_event
from .events.client_events import ClientEvent, ClientEventMode
from .events.events import ServerEvent

from .helpers.intervals import Intervals

class SimplyPrintWebSocket:
    on_event: Callable[[ServerEvent, Optional[int]], None]
    on_disconnect: Callable[[], Awaitable[None]]

    loop: asyncio.AbstractEventLoop
    session: aiohttp.ClientSession
    socket: aiohttp.ClientWebSocketResponse
    intervals: Intervals
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
        ws.on_event = on_event
        ws.on_disconnect = on_disconnect or ws.on_disconnect

        return ws
    
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
        forClient: Optional[int] = event.get("for")
        demand: Optional[str] = data.get("demand")

        try:
            event: ServerEvent = get_event(name, demand, data)
        except KeyError as e:
            self.logger.error(f"Unknown event type {e.args[0]}")
            return
        
        self.logger.debug(f"Recieved event {event} with data {data} for client {forClient}")
        
        self.on_event(event, forClient)

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
                self.logger.debug(f"Did not send event {event} with data {message} because of mode {mode.name}")

        except ConnectionResetError as e:
            self.logger.error(f"Failed to send event {event}: {e}")
            await self.on_disconnect()

    def is_connected(self) -> bool:
        return self.socket is not None and not self.socket.closed
    
    @abstractmethod
    async def on_disconnect(self) -> None:
        self.logger.warn(f"Websocket disconnected with code {self.socket.close_code if self.socket else 'Unknown'}")
