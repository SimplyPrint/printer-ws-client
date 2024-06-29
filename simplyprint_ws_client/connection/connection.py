import asyncio
import json
import logging
from asyncio import CancelledError
from contextlib import suppress
from typing import Any, Dict, Optional, Union

from aiohttp import (ClientSession,
                     ClientWebSocketResponse, WSMsgType,
                     ClientResponseError, ClientError)

from ..client.client import Client
from ..events import DemandEvent, ServerEvent, EventFactory
from ..events.client_events import ClientEvent, ClientEventMode
from ..events.event import Event
from ..events.event_bus import EventBus
from ..utils import issue_118950_patch  # noqa
from ..utils.cancelable_lock import CancelableLock
from ..utils.event_loop_provider import EventLoopProvider
from ..utils.traceability import traceable


class ConnectionPollEvent(Event):
    event: Union[ServerEvent, DemandEvent]
    for_client: Optional[Union[str, int]] = None

    # Some events should be ignored not backlogged.
    # TODO clean this up.
    allow_backlog: bool = True

    def __init__(self, event: Union[ServerEvent, DemandEvent], for_client: Optional[Union[str, int]] = None) -> None:
        self.event = event
        self.for_client = for_client


class ConnectionConnectedEvent(Event):
    reconnect: bool = False

    def __init__(self, reconnect: bool = False) -> None:
        self.reconnect = reconnect


class ConnectionDisconnectEvent(Event):
    ...


class ConnectionEventBus(EventBus[Event]):
    ...


class Connection(EventLoopProvider[asyncio.AbstractEventLoop]):
    logger = logging.getLogger("websocket")

    event_bus: ConnectionEventBus

    ws: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None

    # Ensure only a single thread can connect at a time
    # And we can cancel any connection attempts to enforce
    # the reconnection timeout.
    connection_lock: CancelableLock

    url: Optional[str] = None
    timeout: float = 5.0

    def __init__(self, event_loop_provider: Optional[EventLoopProvider] = None) -> None:
        super().__init__(provider=event_loop_provider)
        self.event_bus = ConnectionEventBus(event_loop_provider=self)
        self.connection_lock = CancelableLock()

    def is_connected(self) -> bool:
        return self.ws is not None and not self.ws.closed

    async def connect(self, url: Optional[str] = None, timeout: Optional[float] = None, allow_reconnects=False) -> None:
        with suppress(asyncio.CancelledError):
            async with self.connection_lock:
                self.use_running_loop()

                reconnected = self.is_connected()

                if reconnected and not allow_reconnects:
                    self.logger.debug("Already connected, not reconnecting as reconnects are not allowed.")
                    return

                if self.ws or self.session:
                    await self.close_internal()
                    self.ws = self.session = None

                self.url = url or self.url
                self.timeout = timeout or self.timeout
                self.session = ClientSession()

                self.logger.debug(
                    f"{'Connecting' if not reconnected else 'Reconnecting'} to {url or self.url}")

                if not self.url:
                    raise ValueError("No url specified")

                ws = None

                try:
                    ws = await self.session.ws_connect(
                        self.url,
                        timeout=timeout,
                        autoclose=True,
                        autoping=True,
                        heartbeat=10,
                        max_msg_size=0,
                        compress=False,
                    )

                except ClientResponseError as e:
                    self.logger.info(f"Failed to connect to {self.url} with status code {repr(e)}")
                except (ConnectionRefusedError, ClientError) as e:
                    self.logger.warning(f"Failed to connect to {self.url} due to a network/client error {e}.")
                except Exception as e:
                    self.logger.error(f"Failed to connect to {self.url} due to an exception {e}.", exc_info=e)

                # Handle disconnect in a new task.
                if ws is None or ws.closed:
                    # Kick out any other connection attempts until this point
                    # and retry the connection via the disconnect event.
                    self.connection_lock.cancel()
                    _ = self.event_bus.emit_task(ConnectionDisconnectEvent())
                    return

                self.ws = ws

                _ = self.event_bus.emit_task(ConnectionConnectedEvent(reconnect=reconnected))

                self.logger.debug(f"Connected to {self.url} {reconnected=}")

    async def close_internal(self):
        try:
            if self.ws:
                await self.ws.close()
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

    async def on_disconnect(self):
        """
                When
                something
                goes
                wrong, reset
                the
                socket
                """

        if self.is_connected():
            await self.close_internal()

        await self.event_bus.emit(ConnectionDisconnectEvent())

    async def send_event(self, client: Client, event: ClientEvent) -> None:
        if not self.is_connected():
            self.logger.debug(
                f"Did not send event {event} because not connected")
            await self.on_disconnect()
            return

        try:
            mode = event.get_client_mode(client)

            if mode != ClientEventMode.DISPATCH:
                # This log is too verbose.
                # self.logger.debug(f"Did not send event {event.get_name()} because of mode {mode.name}")
                return

            message = event.as_dict()

            await self.ws.send_json(message)

            event.on_sent()

            self.logger.debug(f"Sent event {event.get_name()}" if len(
                str(message)) > 1000 else f"Sent event {event} with data {message}")

        except ConnectionResetError as e:
            self.logger.error(f"Failed to send event {event}", exc_info=e)
            await self.on_disconnect()

    @traceable
    async def poll_event(self, timeout=None) -> None:
        if not self.is_connected():
            self.logger.debug(f"Did not poll event because not connected")
            await self.on_disconnect()
            return

        try:
            message = await self.ws.receive(timeout=timeout)

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                self.logger.debug(
                    f"Websocket closed by server with code: {self.ws.close_code} and reason: {message.extra}")

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

            await self.event_bus.emit(ConnectionPollEvent(event, for_client))

        except (CancelledError, TimeoutError, ConnectionResetError):
            self.logger.debug(f"Websocket closed by server due to timeout.")
            await self.on_disconnect()

        except Exception as e:
            self.logger.exception(f"Exception occurred when polling event", exc_info=e)
