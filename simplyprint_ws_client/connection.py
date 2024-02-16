import asyncio
import json
import logging
from asyncio import CancelledError
from typing import Any, Dict, Optional, Union

from aiohttp import (ClientConnectorError, ClientSession,
                     ClientWebSocketResponse, WSMsgType,
                     WSServerHandshakeError)

from .client import Client
from .events import DemandEvent, ServerEvent, EventFactory
from .events.client_events import ClientEvent, ClientEventMode
from .events.event import Event
from .events.event_bus import EventBus


class ConnectionEventReceivedEvent(Event):
    event: Union[ServerEvent, DemandEvent]
    for_client: Optional[Union[str, int]] = None

    def __init__(self, event: Union[ServerEvent, DemandEvent], for_client: Optional[Union[str, int]] = None) -> None:
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

    socket: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None

    # Ensure only a single thread can connect at a time
    connection_lock: asyncio.Lock

    url: Optional[str] = None
    timeout: float = 5.0

    def __init__(self) -> None:
        self.event_bus = ConnectionEventBus()
        self.connection_lock = asyncio.Lock()

    async def connect(self, url: Optional[str] = None, timeout: Optional[float] = None) -> None:
        async with self.connection_lock:
            reconnected = False

            if self.socket:
                await self.close_internal()
                self.socket = self.session = None
                reconnected = True

            self.url = url or self.url
            self.timeout = timeout or self.timeout
            self.session = ClientSession()

            self.logger.debug(
                f"{'Connecting' if not reconnected else 'Reconnecting'} to {url or self.url}")

            if not self.url:
                raise ValueError("No url specified")

            socket = None

            try:
                socket = await self.session.ws_connect(self.url, timeout=timeout, autoclose=False, max_msg_size=0,
                                                       compress=False)
            except WSServerHandshakeError as e:
                self.logger.error(
                    f"Failed to connect to {self.url} with status code {e.status}")
                self.logger.exception(e)
            except ClientConnectorError as e:
                self.logger.error(f"Failed to connect to {self.url}")
                self.logger.exception(e)
            except Exception as e:
                self.logger.exception(e)

            # Handle disconnect in a new task.
            if socket is None or socket.closed:
                _ = self.event_bus.emit_task(ConnectionDisconnectEvent())
                return

            self.socket = socket

            if reconnected:
                self.logger.debug(f"Reconnected to {self.url}")
                await self.event_bus.emit(ConnectionReconnectEvent())
            else:
                self.logger.debug(f"Connected to {self.url}")
                await self.event_bus.emit(ConnectionConnectedEvent())

    async def close_internal(self):
        try:
            if self.socket:
                await self.socket.close()
        except Exception as e:
            self.logger.error("An exception occurred while closing to handle a disconnect condition", exc_info=e)

        try:
            if self.session:
                await self.session.close()

        except Exception as e:
            self.logger.error("An exception occurred while closing to handle a disconnect condition", exc_info=e)

    async def close(self) -> None:
        await self.close_internal()

        self.logger.debug(f"Closed connection to {self.url}")

        await self.on_disconnect()

    def is_connected(self) -> bool:
        return self.socket is not None and not self.socket.closed

    async def on_disconnect(self):
        """ When something goes wrong, reset the socket """

        if self.is_connected():
            await self.close_internal()

        await self.event_bus.emit(ConnectionDisconnectEvent())

    async def send_event(self, client: Client, event: ClientEvent) -> None:
        while not self.is_connected():
            self.logger.debug(
                f"Did not send event {event} because not connected")
            await self.on_disconnect()

        try:
            mode = event.get_client_mode(client)

            if mode != ClientEventMode.DISPATCH:
                # """
                # This debug statement is quite
                # distracting, it can be enabled.
                self.logger.debug(f"Did not send event {event} because of mode {mode.name}")
                # """

                return

            message = event.as_dict()

            await self.socket.send_json(message)

            event.on_sent()

            self.logger.debug(f"Sent event {event.get_name()}" if len(
                str(message)) > 1000 else f"Sent event {event} with data {message}")

        except ConnectionResetError as e:
            self.logger.error(f"Failed to send event {event}", exc_info=e)
            await self.on_disconnect()

    async def poll_event(self, timeout=None) -> None:
        if not self.is_connected():
            self.logger.debug(f"Did not poll event because not connected")
            await self.on_disconnect()
            return

        try:
            message = await self.socket.receive(timeout=timeout)

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                self.logger.debug(
                    f"Websocket closed by server with code: {self.socket.close_code} and reason: {message.extra}")

                # An exception can be passed via the message.data
                if message.data:
                    self.logger.exception(message.data)

                await self.on_disconnect()
                return

            if message.type == WSMsgType.ERROR:
                self.logger.error(f"Websocket error: {message.data}")
                await self.on_disconnect()
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
            for_client: Optional[Union[str, int]] = event.get("for")
            demand: Optional[str] = data.get("demand")

            try:
                event: ServerEvent = EventFactory.get_event(name, demand, data)
            except KeyError as e:
                self.logger.error(f"Unknown event type {e.args[0]}")
                return

            self.logger.debug(
                f"Received event {event.get_name()} with data {message.data} for client {for_client}")

            await self.event_bus.emit(ConnectionEventReceivedEvent(event, for_client))

        except (CancelledError, TimeoutError, ConnectionResetError):
            self.logger.debug(f"Websocket closed by server due to timeout.")
            await self.on_disconnect()

        except Exception as e:
            self.logger.exception(f"Exception occurred when polling event", exc_info=e)
