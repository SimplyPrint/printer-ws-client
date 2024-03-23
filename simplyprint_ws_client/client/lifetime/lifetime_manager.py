from enum import Enum
from typing import Dict

from .lifetime import ClientLifetime, ClientAsyncLifetime
from ..client import Client
from ...utils.stoppable import AsyncStoppable


class LifetimeType(Enum):
    ASYNC = 0

    # SYNC = 1

    def get_cls(self):
        return {
            LifetimeType.ASYNC: ClientAsyncLifetime,
            # LifetimeType.SYNC: ClientSyncLifetime,
        }[self]


class LifetimeManager(AsyncStoppable):
    lifetimes: Dict[Client, ClientLifetime]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lifetimes = {}

    def contains(self, client: Client) -> bool:
        return client in self.lifetimes

    def get(self, client: Client) -> ClientLifetime:
        return self.lifetimes.get(client)

    def add(self, client: Client, lifetime_type: LifetimeType = LifetimeType.ASYNC) -> ClientLifetime:
        lifetime = lifetime_type.get_cls()(client, stoppable=self)
        self.lifetimes[client] = lifetime
        return lifetime

    async def loop(self) -> None:
        while not self.is_stopped():
            # Main manager loop.

            await self.wait(10)

    async def start_lifetime(self, client: Client) -> None:
        lifetime = self.get(client)

        if not lifetime:
            return

        await lifetime.start()

    async def stop_lifetime(self, client: Client) -> None:
        lifetime = self.get(client)

        if not lifetime:
            return

        await lifetime.stop()

    def remove(self, client: Client) -> None:
        lifetime = self.lifetimes.pop(client, None)

        if lifetime is not None:
            lifetime.stop()
