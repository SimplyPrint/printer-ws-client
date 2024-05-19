from typing import Iterable, Optional, Union

from ..client import Client
from ..instance.instance import Instance, TClient, TConfig
from ...connection.connection import ConnectionConnectedEvent
from ...events.client_events import ClientEvent
from ...helpers.url_builder import SimplyPrintURL


class SinglePrinter(Instance[TClient, TConfig]):
    client: Optional[Client[TConfig]] = None

    async def add_client(self, client: TClient) -> None:
        self.set_url(
            str(SimplyPrintURL().ws_url / "p" / str(client.config.id) / str(client.config.token)))

        self.client = client

    def get_client(self, _: Optional[TConfig] = None, **kwargs) -> Union[TClient, None]:
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
        # Mark certain events to always be sent to the server
        self.client.printer.mark_all_changed_dirty()

        await self.consume_backlog(self.client_event_backlog, self.on_client_event)

    async def on_client_event(self, event: ClientEvent, client: Client[TConfig]):
        # Do not send for_client identifier for a single printer connection
        event.for_client = None

        await super().on_client_event(event, client)
