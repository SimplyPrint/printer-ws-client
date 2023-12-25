import json
import logging
import threading
from asyncio import AbstractEventLoop, CancelledError
from typing import Any, Dict, Optional, Union

from aiohttp import (ClientConnectorError, ClientSession,
                     ClientWebSocketResponse, WSMsgType,
                     WSServerHandshakeError)

from .events import DemandEvent, ServerEvent, get_event
from .events.client_events import ClientEvent, ClientEventMode
from .events.event import Event
from .events.event_bus import EventBus


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

    # Ensure only a single thread can connect at a time
    _connection_lock: threading.Lock = threading.Lock()

    url: Optional[str] = None
    timeout: float = 5.0

    def __init__(self, loop: AbstractEventLoop) -> None:
        self.loop = loop
        self.event_bus = ConnectionEventBus()

    def set_url(self, url: str) -> None:
        self.url = url

    async def connect(self, url: Optional[str] = None, session: Optional[ClientSession] = None, timeout: Optional[float] = None) -> None:
        with self._connection_lock:
            
            reconnected = False

            if self.socket:
                await self.socket.close()
                await self.session.close()
                self.socket = None
                self.session = None
                reconnected = True

            self.url = url or self.url
            self.timeout = timeout or self.timeout
            self.session = ClientSession(loop=self.loop)

            self.logger.debug(f"{'Connecting' if not reconnected else 'Reconnecting'} to {url or self.url}")
            
            if not self.url:
                raise ValueError("No url specified")

            socket = None

            try:
                socket = await self.session.ws_connect(self.url, timeout=timeout, autoclose=False, max_msg_size=0, compress=False)
            except WSServerHandshakeError as e:
                self.logger.error(f"Failed to connect to {self.url} with status code {e.status}")
                return
            except ClientConnectorError:
                self.logger.error(f"Failed to connect to {self.url}")
                return
            except Exception as e:
                self.logger.exception(e)
                return
            finally:
                if not socket:
                    await self.event_bus.emit(ConnectionDisconnectEvent())
                    return
                
            self.socket = socket

            if reconnected:
                self.logger.debug(f"Reconnected to {self.url}")
                await self.event_bus.emit(ConnectionReconnectEvent())
            else:
                self.logger.debug(f"Connected to {self.url}")
                await self.event_bus.emit(ConnectionConnectedEvent())

    async def close(self) -> None:
        if self.socket:
            await self.socket.close()
            self.socket = None

        if self.session:
            await self.session.close()
            self.session = None

        self.logger.debug(f"Closed connection to {self.url}")
        await self.event_bus.emit(ConnectionDisconnectEvent())

    def is_connected(self) -> bool:
        return self.socket is not None and not self.socket.closed
    
    async def send_event(self, event: ClientEvent) -> None:
        if not self.is_connected():
            self.logger.debug(f"Did not send event {event} because not connected")
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
            self.logger.debug(f"Did not poll event because not connected")
            await self.event_bus.emit(ConnectionDisconnectEvent())
            return

        try:
            message = await self.socket.receive(timeout=timeout)

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                self.logger.debug(f"Websocket closed by server with code: {self.socket.close_code} and reason: {message.extra}")
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
                f"Recieved event {event} with data {message.data} for client {for_client}")
            
            await self.event_bus.emit(ConnectionEventReceivedEvent(event, for_client))

        except (CancelledError, TimeoutError, ConnectionResetError):
            self.logger.debug(f"Websocket closed by server due to timeout.")
            await self.event_bus.emit(ConnectionDisconnectEvent())