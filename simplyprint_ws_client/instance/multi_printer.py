from asyncio import AbstractEventLoop
from enum import Enum
from typing import Dict, Iterable, Optional, Set

from ..client import Client
from ..config.config import Config
from ..config.manager import ConfigManager
from ..connection import ConnectionConnectedEvent, ConnectionReconnectEvent
from ..const import TEST_WEBSOCKET_URL
from ..events.client_events import (ClientEvent, MachineDataEvent,
                                    StateChangeEvent)
from ..events.server_events import MultiPrinterAddResponseEvent
from .instance import Instance, TClient, TConfig


class MultiPrinterException(RuntimeError):
    pass


class MultiPrinterClientEvents(Enum):
    ADD_PRINTER = "add_connection"
    REMOVE_PRINTER = "remove_connection"


class MultiPrinterAddPrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.ADD_PRINTER

    def __init__(self, config: Config, allow_setup: bool = False) -> None:
        super().__init__(None, None, {
            "pid": config.id if not config.in_setup else 0,
            "token": config.token,
            "unique_id": config.unique_id,
            "allow_setup": allow_setup or False,
            "client_ip": config.public_ip
        })


class MultiPrinterRemovePrinterEvent(ClientEvent):
    event_type = MultiPrinterClientEvents.REMOVE_PRINTER

    def __init__(self, config: Config) -> None:
        super().__init__(None, None, {
            "pid": config.id,
        })


class MultiPrinter(Instance[TClient, TConfig]):
    clients: Dict[str, Client[TConfig]]
    # List of unique ids pending a response from add connection
    pending_unique_set: Set[str]

    def __init__(self, loop: AbstractEventLoop, config_manager: ConfigManager[TConfig], **kwargs) -> None:
        super().__init__(loop, config_manager, **kwargs)

        self.event_bus.on(MultiPrinterAddResponseEvent,
                          self.on_printer_added_response)

        self.connection.set_url(f"{TEST_WEBSOCKET_URL}/mp/0/0")
        self.clients = dict()
        self.pending_unique_set = set()

    async def add_client(self, client: TClient) -> None:
        self.clients[client.config.unique_id] = client

        if not self.connection.is_connected():
            return

        await self._send_add_printer(client)

    async def remove_client(self, client: TClient) -> None:
        if not self.has_client(client):
            return
        
        self.clients.pop(client.config.unique_id)

        if not self.connection.is_connected():
            return

        await self._send_remove_printer(client)

    def get_clients(self) -> Iterable[TClient]:
        return self.clients.values()

    def get_client(self, config: TConfig) -> Optional[TClient]:
        if config.is_blank():
            raise MultiPrinterException("Cannot get client with blank config")

        if config.unique_id in self.clients:
            found = self.clients[config.unique_id]
            return found

        for client in self.clients.values():
            if not client.config.partial_eq(config):
                continue
            return client

    def has_client(self, client: TClient) -> bool:
        return client in self.clients.values()

    def should_connect(self) -> bool:
        return len(self.clients) > 0

    async def on_printer_added_response(self, client: TClient, event: MultiPrinterAddResponseEvent):
        self.pending_unique_set.remove(client.config.unique_id)

        if event.status:
            client.config.id = event.printer_id
            self.config_manager.flush(client.config)

            # Mark certain events to always be sent to the server
            client.printer.mark_event_as_dirty(MachineDataEvent)
            client.printer.mark_event_as_dirty(StateChangeEvent)

            await self.consume_backlog(self.server_event_backlog, self.on_recieved_event)
            await self.consume_backlog(self.client_event_backlog, self.on_client_event)
        else:            
            self.clients.pop(client.config.unique_id, None)

        # Do not propegate event further.
        event.stop_event()

    async def on_connect(self, _: ConnectionConnectedEvent):
        self.pending_unique_set.clear()

        for client in self.clients.values():
            if client.connected:
                continue

            await self._send_add_printer(client)

    async def on_reconnect(self, _: ConnectionReconnectEvent):
        self.pending_unique_set.clear()

        for client in self.clients.values():
            client.connected = False
            await self._send_add_printer(client)


    async def _send_add_printer(self, client: TClient):
        if client.config.unique_id in self.pending_unique_set:
            raise MultiPrinterException(
                f"Cannot add printer with unique id {client.config.unique_id} as it is already in use")

        self.pending_unique_set.add(client.config.unique_id)
        await self.connection.send_event(MultiPrinterAddPrinterEvent(client.config, self.allow_setup))

    async def _send_remove_printer(self, client: TClient):
        await self.connection.send_event(MultiPrinterRemovePrinterEvent(client.config))
