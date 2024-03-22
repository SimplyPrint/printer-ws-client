from typing import Iterable, Optional, Union

from simplyprint_ws_client.const import SimplyPrintUrl
from .instance import Instance, TClient, TConfig
from simplyprint_ws_client.client import Client
from simplyprint_ws_client.connection import ConnectionConnectedEvent, ConnectionReconnectEvent
from simplyprint_ws_client.events.client_events import ClientEvent


class SinglePrinter(Instance[TClient, TConfig]):
    client: Optional[Client[TConfig]] = None

    async def add_client(self, client: TClient) -> None:
        self.set_url(
            str(SimplyPrintUrl.current().ws_url / "p" / client.config.id / client.config.token))

        self.client = client

    def get_client(self, _: TConfig) -> Union[TClient, None]:
        return self.client

    def get_clients(self) -> Iterable[TClient]:
        return [self.client]

    def has_client(self, client: TClient) -> bool:
        return self.client == client

    async def remove_client(self, client: TClient) -> None:
        if not self.has_client(client):
            return

        self.client = None

    def should_connect(self) -> bool:
        return self.client is not None

    async def on_connect(self, _: ConnectionConnectedEvent):
        await self.consume_backlog(self.client_event_backlog, self.on_client_event)

    async def on_reconnect(self, _: ConnectionReconnectEvent):
        # Mark certain events to always be sent to the server
        self.client.printer.mark_all_changed_dirty()

        await self.consume_backlog(self.client_event_backlog, self.on_client_event)

    async def on_client_event(self, event: ClientEvent, client: Client[TConfig]):
        # Do not send for_client identifier for a single printer connection
        event.for_client = None

        await super().on_client_event(event, client)
