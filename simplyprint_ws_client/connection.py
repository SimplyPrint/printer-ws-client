

from asyncio import AbstractEventLoop, CancelledError
from email import message
import json
import logging
import threading
import time
from typing import Any, Dict, Optional, Union

from aiohttp import ClientConnectorError, ClientSession, ClientWebSocketResponse, WSMsgType, WSServerHandshakeError

from .events import DemandEvent, ServerEvent, get_event
from .events.client_events import ClientEvent, ClientEventMode

from .events.event_bus import Event,EventBus

class ConnectionEventReceivedEvent(Event):
    event: Union[ServerEvent, DemandEvent]
    for_client: Optional[int] = None
    
    def __init__(self, event: Union[ServerEvent, DemandEvent], for_client: Optional[int] = None) -> None:
        self.event = event
        self.for_client = for_client

class ConnectionConnectedEvent(Event):
    ...

class ConnectionDisconnectEvent(Event):
    ...

class ConnectionReconnectEvent(Event):
    ...

class ConnectionEventBus(EventBus[Event]):
    ...


class Connection:
    logger = logging.getLogger("websocket")

    event_bus: ConnectionEventBus

    loop: AbstractEventLoop
    socket: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None
    thread_id: int

    # Ensure only a single thread can connect at a time
    _connection_lock: threading.Lock = threading.Lock()

    url: Optional[str] = None
    timeout: float = 5.0

    def __init__(self, loop: AbstractEventLoop) -> None:
        self.loop = loop
        self.thread_id = threading.get_ident()
        self.event_bus = ConnectionEventBus()

    def set_url(self, url: str) -> None:
        self.url = url

    async def connect(self, url: Optional[str] = None, session: Optional[ClientSession] = None, timeout: Optional[float] = None) -> None:
        with self._connection_lock:
            if self.is_connected():
                return

            reconnected = False

            if self.socket:
                await self.socket.close()
                self.socket = None
                reconnected = True

            self.url = url or self.url
            self.timeout = timeout or self.timeout
            self.session = self.session or session or ClientSession(loop=self.loop)

            try:
                self.socket = await self.session.ws_connect(self.url, timeout=timeout, autoclose=False, max_msg_size=0, compress=False)
            except WSServerHandshakeError as e:
                self.logger.error(f"Failed to connect to {self.url} with status code {e.status}")
                return
            except ClientConnectorError:
                self.logger.error(f"Failed to connect to {self.url}")
                return

            if reconnected:
                await self.event_bus.emit(ConnectionReconnectEvent())
                self.logger.debug(f"Reconnected to {self.url}")
            else:
                await self.event_bus.emit(ConnectionConnectedEvent())
                self.logger.debug(f"Connected to {self.url}")

    async def close(self) -> None:
        if self.socket:
            await self.socket.close()
            self.socket = None

        if self.session:
            await self.session.close()
            self.session = None

        await self.event_bus.emit(ConnectionDisconnectEvent())

    def is_connected(self) -> bool:
        return self.socket is not None and not self.socket.closed
    
    async def send_event(self, event: ClientEvent) -> None:
        if not self.is_connected():
            await self.event_bus.emit(ConnectionDisconnectEvent())

        try:
            message = event.as_dict()

            mode = event.on_send()

            if mode != ClientEventMode.DISPATCH:
                self.logger.debug(
                    f"Did not send event {event} with data {message} because of mode {mode.name}")
                 
                return
            
            await self.socket.send_json(message)
            self.logger.debug(f"Sent event {event} with data {message}")
            
        except ConnectionResetError as e:
            self.logger.error(f"Failed to send event {event}: {e}")
            await self.event_bus.emit(ConnectionDisconnectEvent())

    async def poll_event(self, timeout=None) -> None:
        if not self.is_connected():
            await self.event_bus.emit(ConnectionDisconnectEvent())
            return

        try:
            message = await self.socket.receive(timeout=timeout)

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                await self.event_bus.emit(ConnectionDisconnectEvent())
                return
            
            if message.type == WSMsgType.ERROR:
                self.logger.error(f"Websocket error: {str(message.data)}")
                await self.event_bus.emit(ConnectionDisconnectEvent())
                return
            
            if message.type == WSMsgType.BINARY:
                message.data = message.data.decode("utf-8")

            try:
                event: Dict[str, Any] = json.loads(message.data)
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse event: {message.data}")
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
            
            await self.event_bus.emit(ConnectionEventReceivedEvent(event))

        except (CancelledError, TimeoutError, ConnectionResetError):
            await self.event_bus.emit(ConnectionDisconnectEvent())