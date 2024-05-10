import asyncio
import json
import logging
import traceback
from asyncio import CancelledError
from typing import Any, Dict, Optional, Union

from aiohttp import (ClientConnectorError, ClientSession,
                     ClientWebSocketResponse, WSMsgType,
                     WSServerHandshakeError, ClientOSError)

from ..client.client import Client
from ..events import DemandEvent, ServerEvent, EventFactory
from ..events.client_events import ClientEvent, ClientEventMode
from ..events.event import Event
from ..events.event_bus import EventBus
from ..utils import traceability
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

    socket: Optional[ClientWebSocketResponse] = None
    session: Optional[ClientSession] = None

    # Ensure only a single thread can connect at a time
    connection_lock: asyncio.Lock

    url: Optional[str] = None
    timeout: float = 5.0

    def __init__(self, event_loop_provider: Optional[EventLoopProvider] = None) -> None:
        super().__init__(provider=event_loop_provider)
        self.event_bus = ConnectionEventBus(event_loop_provider=self)
        self.connection_lock = asyncio.Lock()

    def is_connected(self) -> bool:
        valid_internal_state = self._ensure_internal_ssl_proto_state()

        if not valid_internal_state:
            self.logger.warning("Internal SSL protocol state is invalid.")

            from asyncio.selector_events import _SelectorTransport
            trace = traceability.from_func(_SelectorTransport._force_close)

            if trace is not None:
                self.logger.warning(f"Found {len(trace.get_call_record())} trace for _SelectorTransport._force_close")

                for record in trace.get_call_record():
                    self.logger.warning(
                        f"""[{record.called_at}] Called _SelectorTransport._force_close with args {record.args} retval {record.retval}. Stack:
                        {''.join(traceback.StackSummary.from_list(record.stack).format()) if record.stack else "No stack"}
                        """)

                trace.call_record.clear()

            return False

        return self.socket is not None and not self.socket.closed

    async def connect(self, url: Optional[str] = None, timeout: Optional[float] = None, allow_reconnects=False) -> None:
        async with self.connection_lock:
            self.use_running_loop()

            if self.is_connected() and not allow_reconnects:
                return

            reconnected = self.is_connected()

            if self.socket or self.session:
                await self.close_internal()
                self.socket = self.session = None

            self.url = url or self.url
            self.timeout = timeout or self.timeout
            self.session = ClientSession()

            self.logger.debug(
                f"{'Connecting' if not reconnected else 'Reconnecting'} to {url or self.url}")

            if not self.url:
                raise ValueError("No url specified")

            socket = None

            try:
                socket = await self.session.ws_connect(
                    self.url,
                    timeout=timeout,
                    autoclose=True,
                    autoping=True,
                    heartbeat=10,
                    max_msg_size=0,
                    compress=False,
                )

            except WSServerHandshakeError as e:
                self.logger.info(
                    f"Failed to connect to {self.url} with status code {e.status}: {e.message}")
            except (ClientConnectorError, ClientOSError) as e:
                self.logger.error(f"Failed to connect to {self.url}", exc_info=e)
            except Exception as e:
                self.logger.exception(e)

            # Handle disconnect in a new task.
            if socket is None or socket.closed:
                _ = self.event_bus.emit_task(ConnectionDisconnectEvent())
                return

            self.socket = socket

            _ = self.event_bus.emit_task(ConnectionConnectedEvent(reconnect=reconnected))
            self.logger.debug(f"Connected to {self.url} {reconnected=}")

    def _ensure_internal_ssl_proto_state(self) -> bool:
        try:
            if not self.socket or not self.socket._writer:
                return True

            from asyncio.sslproto import _SSLProtocolTransport

            transport = self.socket._writer.transport

            if not isinstance(transport, _SSLProtocolTransport):
                return True

            from asyncio.selector_events import _SelectorTransport
            if not isinstance(transport._ssl_protocol._transport, _SelectorTransport):
                return True

            inner_transport = transport._ssl_protocol._transport

            return transport.is_closing() == inner_transport.is_closing()

        except Exception as e:
            self.logger.warning("An exception occurred while ensuring the internal SSL protocol state", exc_info=e)
            return True

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
                self.logger.debug(f"Did not send event {event} because of mode {mode.name}")
                return

            message = event.as_dict()

            await self.socket.send_json(message)

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

            await self.event_bus.emit(ConnectionPollEvent(event, for_client))

        except (CancelledError, TimeoutError, ConnectionResetError):
            self.logger.debug(f"Websocket closed by server due to timeout.")
            await self.on_disconnect()

        except Exception as e:
            self.logger.exception(f"Exception occurred when polling event", exc_info=e)
