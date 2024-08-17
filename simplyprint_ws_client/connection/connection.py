import asyncio
import json
import logging
import time
from asyncio import CancelledError
from contextlib import suppress
from typing import Any, Dict, Optional, Union

from aiohttp import (ClientSession,
                     ClientWebSocketResponse, WSMsgType,
                     ClientResponseError, ClientError)
from yarl import URL

from ..client.client import Client
from ..client.protocol import DemandEvent, ServerEvent, EventFactory
from ..client.protocol.client_events import ClientEvent, ClientEventMode, PingEvent
from ..client.protocol.server_events import PongEvent
from ..events.event import Event
from ..events.event_bus import EventBus
from ..helpers.intervals import IntervalTypes
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
    ignore_connection_criteria: bool = False

    def __init__(self, ignore_connection_criteria: bool = False) -> None:
        self.ignore_connection_criteria = ignore_connection_criteria


ConnectionEventBus = EventBus[Event]


class Connection(EventLoopProvider[asyncio.AbstractEventLoop]):
    logger = logging.getLogger("websocket")

    event_bus: ConnectionEventBus

    ws: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None

    # Ensure only a single thread can connect at a time
    # And we can cancel any connection attempts to enforce
    # the reconnection timeout.
    connection_lock: CancelableLock

    # Keep track of "responsiveness" of the connection
    # And find failures where pings are sent, heartbeats are responded to
    # but no events are received when they need to be.
    last_sent_ping: float = 0.0
    last_received_pong: float = 0.0
    last_received_at: float = 0.0

    url: Union[URL, str, None] = None
    timeout: float = 5.0
    debug: bool = True

    def __init__(self, event_loop_provider: Optional[EventLoopProvider] = None) -> None:
        super().__init__(provider=event_loop_provider)
        self.event_bus = ConnectionEventBus(event_loop_provider=self)
        self.connection_lock = CancelableLock()

    def is_open(self) -> bool:
        """Check if the connection is open."""
        return self.ws is not None and not self.ws.closed

    def is_connected(self) -> bool:
        """We are connected if the connection is open and responsive."""
        return self.is_open() and self.is_responsive()

    def is_responsive(self) -> bool:
        """Check if the connection is responsive by checking if the last pong was received after the last ping.
        The consistency of pings to pongs does not matter as long as the last pong was received after the last ping.
        Otherwise, any events will make this check pass, but if we are not receiving any events but are requesting them
        we should consider the connection non-responsive."""

        # If the last pong was received after the last ping, the connection is responsive.
        if self.last_received_pong >= self.last_sent_ping:
            return True

        time_since_last_ping = time.time() - self.last_sent_ping

        # If we JUST sent a ping inside a timeframe of 1 second, we are still waiting for a pong.
        # So there is no need to consider the connection non-responsive. This prevents unnecessary log spam.                                                
        if time_since_last_ping < 1:
            return True

        time_since_last_received = time.time() - self.last_received_at

        # If we are missing a pong we consider the connection non-responsive after 6x the ping interval
        # since the last received event (could be anything) which is typically 2 minutes.
        if time_since_last_received > IntervalTypes.PING.value.default_timing * 6:
            self.logger.warning(
                "Connection is not responsive as no events has been received for 2 minutes and a pong event is missing."
                f" {self.last_received_pong=} {self.last_sent_ping=} {self.last_received_at=}"
            )

            return False

        # Output a debug message if the connection is potentially unresponsive.
        if self.debug and time_since_last_received > 1:
            self.logger.debug(
                f"Connection is potentially unresponsive! Has not received any events for {time_since_last_received} seconds."
                f" {self.last_received_pong=} {self.last_sent_ping=} {self.last_received_at=}"
            )

        return True

    async def connect(self, url: Union[URL, str, None] = None, timeout: Optional[float] = None,
                      allow_reconnects=False, ignore_connection_criteria=False) -> None:
        with suppress(asyncio.CancelledError):
            async with self.connection_lock:
                self.use_running_loop()

                reconnection = self.is_open()

                if reconnection and not allow_reconnects:
                    self.logger.warning("Already connected, not reconnecting as reconnects are not allowed.")
                    return

                if self.ws or self.session:
                    await self.force_close()
                    self.ws = self.session = None

                self.url = url or self.url
                self.timeout = timeout or self.timeout
                self.session = ClientSession()

                if not self.url:
                    raise ValueError("No URL specified")

                self.logger.info(
                    f"{'Connecting' if not reconnection else 'Reconnecting'} to {self.url}")

                ws = None

                try:
                    ws = await self.session.ws_connect(
                        str(self.url),
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

                    self.logger.debug(f"Emitting disconnect event in another task.")
                    _ = self.event_bus.emit_task(
                        ConnectionDisconnectEvent(ignore_connection_criteria=ignore_connection_criteria))
                    return

                self.ws = ws

                # SAFETY: Only one of these are emitted on connect
                _ = self.event_bus.emit_task(ConnectionConnectedEvent(reconnect=reconnection))

                self.logger.debug(f"Connected to {self.url} {reconnection=}")

    async def force_close(self):
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
        await self.force_close()
        await self.on_disconnect(f"Closed connection to {self.url}")

    async def on_disconnect(self, reason: Optional[str] = None, reconnect=True,
                            ignore_connection_criteria=False) -> None:
        """When something goes wrong, reset the socket"""

        closed = self.ws.closed if self.ws else False
        close_code = self.ws.close_code if self.ws else None

        if self.is_connected():
            await self.force_close()

        if not reason:
            reason = "Unknown"

        self.logger.info(
            f"Disconnected from {self.url} due to: '{reason}' {closed=} {close_code=}"
            f"{reconnect=} {ignore_connection_criteria=}"
        )

        if reconnect:
            await self.event_bus.emit(ConnectionDisconnectEvent(ignore_connection_criteria=ignore_connection_criteria))

    async def send_event(self, client: Client, event: ClientEvent) -> None:
        if not self.is_connected():
            await self.on_disconnect(f"Did not send event {event} because not connected")
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

            if isinstance(event, PingEvent):
                self.last_sent_ping = time.time()

            if self.debug:
                self.logger.debug(f"Sent event {event.get_name()}" if len(
                    str(message)) > 1000 else f"Sent event {event} with data {message}")

        except ConnectionResetError as e:
            await self.on_disconnect(f"Failed to send event {event}")
            self.logger.exception(e)

    @traceable
    async def poll_event(self, timeout=None) -> None:
        if not self.is_connected():
            await self.on_disconnect(f"Did not poll event because not connected")
            return

        try:
            message = await self.ws.receive(timeout=timeout)

            self.last_received_at = time.time()

            if message.type in (WSMsgType.CLOSED, WSMsgType.CLOSING, WSMsgType.CLOSE):
                self.logger.debug(
                    f"Websocket closed by server with code: {self.ws.close_code}. {message.data=} {message.extra=}")

                # An exception can be passed via the message.data
                if isinstance(message.data, Exception):
                    self.logger.exception(message.data)

                await self.on_disconnect("Websocket closed by server.")
                return

            if message.type == WSMsgType.ERROR:
                await self.on_disconnect(f"Websocket error: {message.data}")
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

            if isinstance(event, PongEvent):
                self.last_received_pong = self.last_received_at

            if self.debug:
                self.logger.debug(
                    f"Received event {event.get_name()} with data {message.data} for client {for_client}")

            await self.event_bus.emit(ConnectionPollEvent(event, for_client))

        except (CancelledError, TimeoutError, ConnectionResetError):
            await self.on_disconnect(f"Websocket closed by server due to timeout.")

        except Exception as e:
            self.logger.exception(f"Exception occurred when polling event", exc_info=e)
