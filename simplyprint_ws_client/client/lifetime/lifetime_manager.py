import logging
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
    logger: logging.Logger
    lifetime_check_interval = 10
    lifetimes: Dict[Client, ClientLifetime]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("lifetime_manager")
        self.lifetimes = {}

    def contains(self, client: Client) -> bool:
        return client in self.lifetimes

    def get(self, client: Client) -> ClientLifetime:
        return self.lifetimes.get(client)

    def add(self, client: Client, lifetime_type: LifetimeType = LifetimeType.ASYNC) -> ClientLifetime:
        if self.is_stopped():
            raise RuntimeError("Lifetime manager is stopped - cannot add new lifetimes")

        if self.contains(client):
            return self.get(client)

        lifetime = lifetime_type.get_cls()(client, parent_stoppable=self)
        self.lifetimes[client] = lifetime
        return lifetime

    async def loop(self) -> None:
        self.logger.info("Starting lifetime manager loop")

        while not self.is_stopped():
            for client, lifetime in list(self.lifetimes.items()):
                # TODO retry the lifetime in a bit...
                if lifetime.is_stopped():
                    continue

                if lifetime.is_healthy():
                    continue

                client.logger.warning(f"Client lifetime unhealthy - restarting")

                await self.stop_lifetime(client)
                await self.start_lifetime(client)

            await self.wait(self.lifetime_check_interval)

        self.logger.info("Lifetime manager loop stopped - stopping all lifetimes")

        for client, lifetime in list(self.lifetimes.items()):
            await self.stop_lifetime(client)

        self.logger.info("Lifetime manager loop stopped")

    async def start_lifetime(self, client: Client) -> None:
        if self.is_stopped():
            raise RuntimeError("Lifetime manager is stopped - cannot start new lifetimes")

        lifetime = self.get(client)

        if not lifetime:
            return

        await lifetime.start()

    async def stop_lifetime(self, client: Client) -> None:
        lifetime = self.get(client)

        if not lifetime:
            return

        lifetime.stop()

    def remove(self, client: Client) -> None:
        lifetime = self.lifetimes.pop(client, None)

        if lifetime is not None:
            lifetime.stop()
