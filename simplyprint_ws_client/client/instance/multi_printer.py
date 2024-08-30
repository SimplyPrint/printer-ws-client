import asyncio
from enum import Enum
from typing import Dict, Iterable, Optional, Set

from ..client import Client
from ..config import ConfigManager
from ..config import PrinterConfig
from ..instance.instance import Instance, TClient, TConfig, InstanceException
from ..protocol.client_events import ClientEvent
from ..protocol.server_events import MultiPrinterAddedEvent, MultiPrinterRemovedEvent
from ...connection.connection import ConnectionConnectedEvent, ConnectionPollEvent, ConnectionDisconnectEvent
from ...helpers.url_builder import SimplyPrintURL
from ...utils.predicate import IsInstance, Extract, Eq
from ...utils.property_path import p

# The way we have designed these protocols is that the server will always respond to the client
# so in the case no response is received, we can assume the server has not received the request
# or a failure occurred under transport. Since we catch this category of errors with heartbeats and
# other mechanisms, we can set this timeout to be VERY high, so there is still some chance of automatic
# failure recovery.
_DEFAULT_REQUEST_NOT_RECEIVED_TIMEOUT = 1800


class MultiPrinterException(InstanceException):
    pass


class MultiPrinterFailedToAddException(MultiPrinterException):
    ...


class MultiPrinterClientEvents(Enum):
    ADD_PRINTER = "add_connection"
    REMOVE_PRINTER = "remove_connection"


class MultiPrinterAddPrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.ADD_PRINTER

    def __init__(self, config: PrinterConfig, allow_setup: bool = False) -> None:
        super().__init__({
            "pid":         config.id if not config.in_setup else 0,
            "token":       config.token,
            "unique_id":   config.unique_id,
            "allow_setup": allow_setup or False,
            "client_ip":   config.public_ip
        })


class MultiPrinterRemovePrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.REMOVE_PRINTER

    def __init__(self, config: PrinterConfig) -> None:
        super().__init__({
            "pid":       config.id,
            "unique_id": config.unique_id,
        })


class MultiPrinter(Instance[TClient, TConfig]):
    clients: Dict[str, Client[TConfig]]

    # Set of futures to cancel when the connection is reset.
    _pending_connection_waiters: Set[asyncio.Future]

    def __init__(self, config_manager: ConfigManager[TConfig], **kwargs) -> None:
        super().__init__(config_manager, **kwargs)

        # We can receive unsolicited printer removal requests from the server
        # So we cannot handle them 1:1 with our own removal requests.
        self.event_bus.on(MultiPrinterRemovedEvent, self.on_printer_removed_response, priority=10)

        self.clients = dict()
        self._pending_connection_waiters = set()

    @property
    def url(self):
        return SimplyPrintURL().ws_url / "mp" / "0" / "0"

    async def add_client(self, client: TClient) -> None:
        try:
            # Wait for the response to be received.
            # This function adds the printer to self.clients
            # And manages the state by serializing it under the client lock
            # in one go.
            event = await self._request_add_printer(client)

            if not event.status:
                raise MultiPrinterFailedToAddException(f"Failed to add printer {client.config.unique_id}")

        except (asyncio.TimeoutError, asyncio.CancelledError):
            raise MultiPrinterException(f"Failed to add printer {client.config.unique_id} due to timeout/cancellation.")

    async def deregister_client(self, client: TClient, remove_from_config=False, request_removal=True):
        await super().deregister_client(client, remove_from_config)

        if not request_removal:
            return

        # We cannot remove a printer if we are not connected.
        if not self.connection.is_connected():
            return

        try:
            await self._request_remove_printer(client)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            raise MultiPrinterException(f"Failed to remove printer {client.config.unique_id} due to timeout.")

    async def remove_client(self, client: TClient) -> None:
        if not self.has_client(client):
            return

        self.logger.debug(f"Removing client {client.config.unique_id} from clients.")
        self.clients.pop(client.config.unique_id)

    def get_clients(self) -> Iterable[TClient]:
        return self.clients.values()

    def get_client(self, config: Optional[TConfig] = None, **kwargs) -> Optional[TClient]:
        if config:
            kwargs.update(config.as_dict())

        if not kwargs:
            return None

        if (unique_id := kwargs.get('unique_id')) in self.clients:
            return self.clients[unique_id]

        for client in list(self.clients.values()):
            if not client.config.partial_eq(config, **kwargs):
                continue

            return client

    def has_client(self, client: TClient) -> bool:
        return client in self.clients.values()

    def should_connect(self) -> bool:
        return len(self.clients) > 0

    async def on_poll_event(self, event: ConnectionPollEvent):
        # Prevent issue where MultiPrinterRemoved event is echoed back to us
        # then backlogged were it is reprocessed when the client is re-added.
        if event.event in (MultiPrinterAddedEvent, MultiPrinterRemovedEvent):
            event.allow_backlog = False

        await super().on_poll_event(event)

    async def on_connect(self, event: ConnectionConnectedEvent):
        # Ensure we are not connecting and disconnecting at the same time.
        async with self.disconnect_lock:
            self._reset_connection_waiters()

            for client in list(self.clients.values()):
                if event.reconnect:
                    client.connected = False
                elif client.connected:
                    continue

                # We cannot block inside on_connect as connect() awaits on_connect,
                # and send add printer awaits connect.
                # which will make the waiters never be resolved.
                # Instead, we ensure that all of these tasks are run to completion in the event loop.
                # SAFETY: This does not leak as it is bounded by an upper timeout limit.
                _ = self.event_loop.create_task(self._request_add_printer(client))

    async def on_disconnect(self, event: ConnectionDisconnectEvent):
        async with self.disconnect_lock:
            # Remove pending add waiters when we disconnect.
            self._reset_connection_waiters()

        # Then proceed with reconnection logic.
        await super().on_disconnect(event)

    async def on_printer_removed_response(self, event: MultiPrinterRemovedEvent, client: TClient):
        # Do not propagate event further.
        event.stop_event()

        # Processing an event that already have had their client removed.
        if not client:
            return

        client = self.clients.pop(client.config.unique_id, None)

        if not client:
            return

        self.logger.debug(f"Popped client {client.config.unique_id} from clients due to remove event.")
        client.connected = False

        # If the printer was deleted handle.
        if event.deleted:
            client.config.id = 0
            client.config.in_setup = True
            client.config.short_id = None

            self.config_manager.flush(client.config)

        # TODO is this correct in our new provider model?
        await self.wait(self.reconnect_timeout)

        # Attempt to reconnect the client.
        # The idea is to make the client pending again.
        try:
            await self.register_client(client)
        except InstanceException:
            pass

    def _reset_connection_waiters(self):
        for fut in self._pending_connection_waiters:
            fut.cancel()

        self._pending_connection_waiters.clear()

    async def _request_add_printer(self, client: TClient, timeout=_DEFAULT_REQUEST_NOT_RECEIVED_TIMEOUT) -> Optional[
        MultiPrinterAddedEvent]:
        """TODO: Document this."""
        # We do not add printers before we are connected.
        # Therefore, we need to ignore the connect criteria.
        # Alternatively we could directly invoke connection.connect
        # but this seems more elegant.
        if not self.connection_is_ready.is_set():
            await self.connect(ignore_connect_criteria=True, block_until_connected=True)

        async with client:
            # If the client is already connected, we can skip the add printer event.
            if client.connected and self.has_client(client):
                return None

            fut = self.event_bus_response.create_response(
                IsInstance(MultiPrinterAddedEvent),
                Extract(p.unique_id) | Eq(client.config.unique_id))

            try:
                self._pending_connection_waiters.add(fut)

                await self.connection.send_event(client, MultiPrinterAddPrinterEvent(client.config, self.allow_setup))

                # Add a timeout to the future waiting for the servers' response.
                # This is the worst case precaution which should only deal with the edge case
                # that is we drop the add_connection event on the server side, this way the
                # client can retry again at a later time, usually when the server does not respond
                # NO printers are added, so this is a very rare edge case.
                args, _ = await asyncio.wait_for(fut, timeout=timeout)

                assert isinstance(args[0], MultiPrinterAddedEvent)

                event = args[0]

                event.stop_event()

                if event.status:
                    # This adds the client. Very important.
                    self.clients[client.config.unique_id] = client

                    # For multi-printer we can mark a client as connected
                    # when it was successfully added.
                    client.connected = True
                    client.config.id = event.printer_id

                    self.config_manager.flush(client.config)
                    client.printer.mark_all_changed_dirty()

                    await self.consume_backlog(self.server_event_backlog, self.on_poll_event)
                    await self.consume_backlog(self.client_event_backlog, self.on_client_event)
                else:
                    self.logger.debug(
                        f"Popped client {client.config.unique_id} from clients due to failed adding, status false.")

                    # Ensure the client is removed.
                    try:
                        await self.deregister_client(client, remove_from_config=False, request_removal=False)
                    except InstanceException:
                        ...

                    # TODO awaiting response codes from add_connection
                    # Make printer pending when failed to add.
                    if not client.config.is_pending():
                        ...

                return event
            finally:
                if not fut.done():
                    self.logger.warning(f"Request to add printer {client.config.unique_id} timed out.")

                self._pending_connection_waiters.discard(fut)

    async def _request_remove_printer(self, client: TClient, timeout=_DEFAULT_REQUEST_NOT_RECEIVED_TIMEOUT) -> Optional[MultiPrinterRemovedEvent]:
        """
        Remove events are handled by the event listener on_printer_removed_response,
        but we serialise requests made from the client with the client lock to prevent additions.
        """
        async with client:
            fut = self.event_bus_response.create_response(IsInstance(MultiPrinterRemovedEvent),
                                                          Extract(p.unique_id) | Eq(client.config.unique_id))
            try:
                self._pending_connection_waiters.add(fut)
                await self.connection.send_event(client, MultiPrinterRemovePrinterEvent(client.config))
                args, _ = await asyncio.wait_for(fut, timeout=timeout)
                assert isinstance(args[0], MultiPrinterRemovedEvent)
                event = args[0]
                await self.on_printer_removed_response(event, client)
                return event
            finally:
                if not fut.done():
                    self.logger.warning(f"Request to remove printer {client.config.unique_id} timed out.")

                self._pending_connection_waiters.discard(fut)
