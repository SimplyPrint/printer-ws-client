"""
Class managing connection strategies.

Supports two functionalities.

- Allocate client
- Deallocate client

"""

__all__ = ["ClientConnectionManager"]

import asyncio
import functools
from typing import final, Dict, Optional, Set, cast, Iterable

from .client import Client, ClientState
from .client_list import ClientList, TUniqueId
from .client_view import ClientView
from .config import PrinterConfig
from .ws_protocol.connection import ConnectionMode, Connection, ConnectionHint
from .ws_protocol.events import ConnectionOutgoingEvent, ConnectionIncomingEvent, \
    ConnectionEstablishedEvent, ConnectionLostEvent
from .ws_protocol.messages import ClientMsg
from ..events.event_bus_listeners import ListenerUniqueness
from ..shared.asyncio.event_loop_provider import EventLoopProvider
from ..shared.utils.stoppable import AsyncStoppable


@final
class ClientConnectionManager(AsyncStoppable, EventLoopProvider[asyncio.AbstractEventLoop]):
    """

    Attributes:
        mode: ConnectionMode
        client_list: Global list of clients (immutable from this context)
        client_views: Mapping of client unique_id to client view
        views: Set of all client views
    """

    mode: ConnectionMode
    client_list: ClientList
    client_views: Dict[TUniqueId, ClientView]
    views: Set[ClientView]

    def __init__(
            self,
            mode: ConnectionMode,
            client_list: ClientList,
            **kwargs
    ):
        AsyncStoppable.__init__(self, **kwargs)
        EventLoopProvider.__init__(self, **kwargs)

        self.mode = mode
        self.client_list = client_list
        self.client_views = {}
        self.views = set()

    def _allocate_new_connection(self) -> ClientView:
        if self.is_stopped():
            raise RuntimeError("Cannot allocate connections when stopped.")

        # TODO Logic for using existing connection.
        # For now we have many single connections and one multi.
        if self.mode == ConnectionMode.MULTI and len(self.views) > 0:
            return next(iter(self.views))

        # Creating a new connection / client view pair.
        connection = Connection(provider=self)
        client_view = ClientView(self.mode, connection, self.client_list)
        self.views.add(client_view)

        # Registering the connection with the client view.
        connection.event_bus.on(ConnectionIncomingEvent, functools.partial(client_view.emit, ConnectionIncomingEvent),
                                unique=ListenerUniqueness.EXCLUSIVE_WITH_ERROR)

        connection.event_bus.on(ConnectionEstablishedEvent,
                                client_view.emit,
                                unique=ListenerUniqueness.EXCLUSIVE_WITH_ERROR)

        connection.event_bus.on(ConnectionLostEvent, client_view.emit,
                                unique=ListenerUniqueness.EXCLUSIVE_WITH_ERROR)

        return client_view

    def _derive_connection_hint(self, client: Client) -> ConnectionHint:
        # Use up-to-date credentials to connect.
        # p/id/token else mp/0/0
        is_single = self.mode == ConnectionMode.SINGLE

        return ConnectionHint(
            mode=self.mode,
            config=client.config if is_single else PrinterConfig.get_blank())

    @property
    def connections(self) -> Iterable[Connection]:
        return map(lambda x: cast(ClientView, x).connection, list(self.views))

    def get_connection_for_client(self, client: Client) -> Optional[Connection]:
        view = self.client_views.get(client.unique_id)

        if not view:
            return None

        return view.connection

    def is_allocated(self, client: Client) -> bool:
        return client.unique_id in self.client_views

    async def allocate(self, client: Client) -> None:
        """Allocate a connection and instrument the client with it."""
        if self.is_allocated(client):
            return

        view = self._allocate_new_connection()
        connection = view.connection

        if connection.connected:
            client.v = connection.v
            client.state = ClientState.NOT_CONNECTED

        self.client_views[client.unique_id] = view
        view.add(client)

        if self.mode == ConnectionMode.MULTI:
            # Bind unique_id to the handler.
            def transform_message_with_unique_id(message: ClientMsg, *args, unique_id=client.unique_id):
                message.for_client = unique_id
                return (message,) + args

            client.event_bus.on(ConnectionOutgoingEvent, transform_message_with_unique_id, priority=10)

        client.event_bus.on(ConnectionOutgoingEvent,
                            functools.partial(connection.event_bus.emit, ConnectionOutgoingEvent))

        await connection.connect(hint=self._derive_connection_hint(client))

    async def deallocate(self, client: Client):
        """Deallocate a connection and remove it from the client."""
        if client.unique_id not in self.client_views:
            return

        client_view = self.client_views.pop(client.unique_id)
        client_view.discard(client)
        client.event_bus.clear(ConnectionOutgoingEvent)

        # Disconnect the connection if no clients are left.
        if len(client_view) == 0:
            await client_view.connection.disconnect()

    def stop(self):
        super().stop()

        for connection in self.connections:
            connection.stop()
