__all__ = ["ClientView"]

import logging
from typing import Union, Hashable, Set, MutableSet

from .client import Client
from .client_list import ClientList, TUniqueId
from .ws_protocol.connection import ConnectionMode, Connection
from .ws_protocol.events import ConnectionIncomingEvent, \
    ConnectionEstablishedEvent
from .ws_protocol.messages import MultiPrinterAddedMsg, MultiPrinterRemovedMsg, Msg, ConnectedMsg
from ..events.emitter import Emitter, TEvent


class ClientView(Emitter, MutableSet[Client], Hashable):
    """View over a set of clients, deals with connection message routing."""

    mode: ConnectionMode
    connection: Connection
    client_list: ClientList
    clients: Set[TUniqueId]
    logger: logging.Logger

    def __init__(self, mode: ConnectionMode, connection: Connection, client_list: ClientList,
                 logger=logging.getLogger(__name__)):
        self.mode = mode
        self.connection = connection
        self.client_list = client_list
        self.clients = set()
        self.logger = logger

    async def _emit_all(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        for client in self:
            await client.event_bus.emit(event, *args, **kwargs)

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        # Only handle connection events when we have at least one client.
        if len(self) == 0:
            return

        is_multi_mode = self.mode == ConnectionMode.MULTI

        # Custom handling for incoming messages
        # when we have multiple clients.
        if is_multi_mode and event == ConnectionIncomingEvent:
            if len(args) != 2:
                return

            msg, v = args

            if not isinstance(msg, Msg):
                return

            # For multi-printer connections the `connected` message is the `established` message.
            if isinstance(msg, ConnectedMsg) and msg.for_client is None:
                self.logger.debug("Converted base ConnectedMsg to ConnectionEstablishedEvent with v: %d.", v)
                await self._emit_all(ConnectionEstablishedEvent(v))
                return

            # We can get a routing hint from the message directly.
            client_id = msg.for_client

            # Some messages are targeting the top level connection,
            # but we can further route them to the correct client.
            if client_id is None and isinstance(msg, (MultiPrinterAddedMsg, MultiPrinterRemovedMsg)):
                client_id = msg.data.unique_id

            if client_id not in self.clients:
                return

            await self.client_list[client_id].event_bus.emit(event, *args, **kwargs)

            return

        if is_multi_mode and isinstance(event, ConnectionEstablishedEvent):
            self.logger.debug(
                "Dropped ConnectionEstablishedEvent for multi-mode connection with v: %d in favor of ConnectedMsg",
                event.v)
            return

        # Default handling for all other events.
        await self._emit_all(event, *args, **kwargs)

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        raise NotImplementedError("Use emit() instead.")

    def add(self, value: Client):
        self.clients.add(value.unique_id)

    def discard(self, value: Client):
        self.clients.discard(value.unique_id)

    def __contains__(self, x: Client):
        return x.unique_id in self.clients

    def __len__(self):
        return len(self.clients)

    def __iter__(self):
        for client in self.clients:
            yield self.client_list[client]

    def __hash__(self):
        return hash(id(self))
