import asyncio
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple, Type

from ..client import Client
from ..config import ConfigManager
from ..config import PrinterConfig
from ..instance.instance import Instance, TClient, TConfig, InstanceException
from ..protocol.client_events import ClientEvent
from ..protocol.server_events import MultiPrinterAddedEvent, MultiPrinterRemovedEvent
from ...connection.connection import ConnectionConnectedEvent, ConnectionPollEvent, ConnectionDisconnectEvent
from ...helpers.url_builder import SimplyPrintURL


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

    """
    Dictionary of event type that a client is waiting to receive.
    So event will contain the response, in a certain time frame.
    When a connection is reset all of these are cancelled.
    
        ("add_connection", "unique_id") => fut
        event = await fut

    """
    pending_waiters: Dict[Tuple[Type, str], asyncio.Future]

    def __init__(self, config_manager: ConfigManager[TConfig], **kwargs) -> None:
        super().__init__(config_manager, **kwargs)

        self.event_bus.on(MultiPrinterAddedEvent, self.on_printer_added_response, priority=10)
        self.event_bus.on(MultiPrinterRemovedEvent, self.on_printer_removed_response, priority=10)
        self.clients = dict()
        self.pending_add_waiters = dict()

    @property
    def url(self):
        return SimplyPrintURL().ws_url / "mp" / "0" / "0"

    async def add_client(self, client: TClient) -> None:
        # Will be removed by the response event.
        # But we still raise the exception to trigger
        # any retry logic that might exist.
        self.clients[client.config.unique_id] = client

        added_future = await self._send_add_printer(client)

        # Wait for the response to be received.
        try:
            success = await added_future

            if not success:
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

        await self._send_remove_printer(client)

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
        # Prevent issue where MultiPrinterRemove event is echoed back to us
        # then backlogged were it is reprocessed when the client is re-added.
        if event.event in [MultiPrinterAddedEvent, MultiPrinterRemovedEvent]:
            event.allow_backlog = False

        await super().on_poll_event(event)

    async def on_printer_added_response(self, event: MultiPrinterAddedEvent, client: TClient):
        fut = self.pending_add_waiters.get(client.config.unique_id)
        del self.pending_add_waiters[client.config.unique_id]

        if fut and not fut.done():
            fut.set_result(event.status)

        if event.status:
            # For multi-printer we can mark a client as connected
            # when it was successfully added.
            async with client:
                client.connected = True
                client.config.id = event.printer_id

            self.config_manager.flush(client.config)
            client.printer.mark_all_changed_dirty()

            await self.consume_backlog(self.server_event_backlog, self.on_poll_event)
            await self.consume_backlog(self.client_event_backlog, self.on_client_event)
        else:
            self.logger.debug(
                f"Popped client {client.config.unique_id} from clients due to failed adding, status false.")

            await self.deregister_client(client, remove_from_config=False, request_removal=False)

            # TODO awaiting response codes from add_connection
            # Make printer pending when failed to add.
            if not client.config.is_pending():
                ...

        # Do not propagate event further.
        event.stop_event()

    async def on_printer_removed_response(self, event: MultiPrinterRemovedEvent, client: TClient):
        client = self.clients.pop(client.config.unique_id, None)
        self.logger.debug(f"Popped client {client.config.unique_id} from clients due to remove event.")

        # Do not propagate event further.
        event.stop_event()

        if not client:
            return

        # If the printer was deleted handle.
        if event.deleted:
            async with client:
                client.config.id = 0
                client.config.in_setup = True
                client.config.short_id = None

                self.config_manager.flush(client.config)

        # Attempt to reconnect the client.
        # TODO is this correct in our new provider model?
        await self.wait(self.reconnect_timeout)

        try:
            await self.register_client(client)
        except InstanceException:
            pass

    async def on_connect(self, event: ConnectionConnectedEvent):
        # Ensure we are not connecting and disconnecting at the same time.
        async with self.disconnect_lock:
            for client in list(self.clients.values()):
                async with client:
                    if event.reconnect:
                        client.connected = False

                    elif client.connected:
                        continue

                task = self.pending_add_waiters.get(client.config.unique_id)

                if not task:
                    # We cannot block inside on_connect as connect() awaits on_connect,
                    # and send add printer awaits connect.
                    # which will make the waiters never be resolved.
                    # Instead, we ensure that all of these tasks are run to completion in the event loop.
                    # SAFETY: This does not leak as it is bounded by an upper timeout limit.
                    _ = self.event_loop.create_task(self._send_add_printer(client))

    async def on_disconnect(self, _: ConnectionDisconnectEvent):
        async with self.disconnect_lock:
            # Remove pending add waiters when we disconnect.
            for pending in list(self.pending_add_waiters.keys()):
                task = self.pending_add_waiters.pop(pending, None)
                task.cancel()

        # Then proceed with reconnection logic.
        await super().on_disconnect(_)

    async def _send_add_printer(self, client: TClient) -> asyncio.Future:
        async with client:
            # Lock the pending client before waiting for connect, to ensure on_connect does not compete.
            if client.config.unique_id in self.pending_add_waiters:
                raise MultiPrinterException(
                    f"Cannot add printer with unique id {client.config.unique_id} as it is already pending.")

            fut = self.pending_add_waiters[client.config.unique_id] = self.event_loop.create_future()

        # We do not add printers before we are connected.
        # Therefore, we need to ignore the connect criteria.
        # Alternatively we could directly invoke connection.connect
        # but this seems more elegant.
        if not self.connection.is_connected():
            await self.connect(ignore_connect_criteria=True)

        await self.connection.send_event(client, MultiPrinterAddPrinterEvent(client.config, self.allow_setup))

        # Add a timeout to the future waiting for the servers' response.
        # This is the worst case precaution which should only deal with the edge case
        # that is we drop the add_connection event on the server side, this way the
        # client can retry again at a later time, usually when the server does not respond
        # NO printers are added, so this is a very rare edge case.
        return asyncio.shield(asyncio.wait_for(fut, timeout=60))

    async def _send_remove_printer(self, client: TClient):
        await self.connection.send_event(client, MultiPrinterRemovePrinterEvent(client.config))
