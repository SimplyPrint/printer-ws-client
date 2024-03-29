from enum import Enum
from typing import Dict, Iterable, Optional, Set

from simplyprint_ws_client.client.client import Client
from simplyprint_ws_client.client.config import Config
from simplyprint_ws_client.client.config import ConfigManager
from simplyprint_ws_client.client.instance.instance import Instance, TClient, TConfig, InstanceException
from simplyprint_ws_client.connection.connection import ConnectionConnectedEvent, ConnectionReconnectEvent, \
    ConnectionPollEvent
from simplyprint_ws_client.events.client_events import ClientEvent
from simplyprint_ws_client.events.server_events import MultiPrinterAddedEvent, MultiPrinterRemovedEvent
from simplyprint_ws_client.helpers.url_builder import SimplyPrintUrl


class MultiPrinterException(InstanceException):
    pass


class MultiPrinterClientEvents(Enum):
    ADD_PRINTER = "add_connection"
    REMOVE_PRINTER = "remove_connection"


class MultiPrinterAddPrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.ADD_PRINTER

    def __init__(self, config: Config, allow_setup: bool = False) -> None:
        super().__init__({
            "pid": config.id if not config.in_setup else 0,
            "token": config.token,
            "unique_id": config.unique_id,
            "allow_setup": allow_setup or False,
            "client_ip": config.public_ip
        })


class MultiPrinterRemovePrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.REMOVE_PRINTER

    def __init__(self, config: Config) -> None:
        super().__init__({
            "pid": config.id,
        })


class MultiPrinter(Instance[TClient, TConfig]):
    clients: Dict[str, Client[TConfig]]

    # List of unique ids pending a response from add connection
    pending_unique_set: Set[str]

    def __init__(self, config_manager: ConfigManager[TConfig], **kwargs) -> None:
        super().__init__(config_manager, **kwargs)

        self.event_bus.on(MultiPrinterAddedEvent, self.on_printer_added_response, priority=10)
        self.event_bus.on(MultiPrinterRemovedEvent, self.on_printer_removed_response, priority=10)

        self.set_url(str(SimplyPrintUrl.current().ws_url / "mp" / 0 / 0))

        self.clients = dict()
        self.pending_unique_set = set()

    async def add_client(self, client: TClient) -> None:
        self.clients[client.config.unique_id] = client

        if not self.connection.is_connected():
            return

        await self._send_add_printer(client)

    async def deregister_client(self, client: TClient, remove_from_config=False, request_removal=True):
        await super().deregister_client(client, remove_from_config)

        if not request_removal:
            return

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

    def get_client(self, config: TConfig) -> Optional[TClient]:
        if config.is_blank():
            return None

        if config.unique_id in self.clients:
            return self.clients[config.unique_id]

        for client in self.clients.values():
            if not client.config.partial_eq(config):
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
        self.pending_unique_set.discard(client.config.unique_id)

        if event.status:
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
            client.config.id = 0
            client.config.in_setup = True
            client.config.short_id = None

            self.config_manager.flush(client.config)

        # Attempt to reconnect the client.
        await self.wait(self.reconnect_timeout)

        try:
            await self.register_client(client)
        except InstanceException:
            pass

    async def on_connect(self, _: ConnectionConnectedEvent):
        self.pending_unique_set.clear()

        for client in self.clients.values():
            if client.connected:
                continue

            await self._send_add_printer(client)

    async def on_reconnect(self, _: ConnectionReconnectEvent):
        self.pending_unique_set.clear()

        for client in self.clients.values():
            async with client:
                client.connected = False
                await self._send_add_printer(client)

    async def _send_add_printer(self, client: TClient):
        if client.config.unique_id in self.pending_unique_set:
            raise MultiPrinterException(
                f"Cannot add printer with unique id {client.config.unique_id} as it is already in use")

        self.pending_unique_set.add(client.config.unique_id)
        await self.connection.send_event(client, MultiPrinterAddPrinterEvent(client.config, self.allow_setup))

    async def _send_remove_printer(self, client: TClient):
        await self.connection.send_event(client, MultiPrinterRemovePrinterEvent(client.config))
