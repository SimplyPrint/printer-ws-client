import logging
from enum import Enum
from typing import Dict, TYPE_CHECKING

from .lifetime import ClientLifetime, ClientAsyncLifetime
from ..client import Client
from ...utils.stoppable import AsyncStoppable

if TYPE_CHECKING:
    from ..instance import Instance


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

    instance: 'Instance'
    lifetimes: Dict[str, ClientLifetime]

    def __init__(self, instance: 'Instance', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = instance.logger.getChild("lifetime_manager")
        self.instance = instance
        self.lifetimes = {}

    def contains(self, client: Client) -> bool:
        return client.config.unique_id in self.lifetimes

    def get(self, client: Client) -> ClientLifetime:
        return self.lifetimes.get(client.config.unique_id)

    def add(self, client: Client, lifetime_type: LifetimeType = LifetimeType.ASYNC) -> ClientLifetime:
        if self.is_stopped():
            raise RuntimeError("Lifetime manager is stopped - cannot add new lifetimes")

        if self.contains(client):
            return self.get(client)

        lifetime = lifetime_type.get_cls()(self, client)
        self.lifetimes[client.config.unique_id] = lifetime
        return lifetime

    def should_consume(self, _client: Client) -> bool:
        return self.instance.connection_is_ready.is_set()

    async def loop(self) -> None:
        self.logger.info("Starting lifetime manager loop")

        # Start after a delay as this is just a manager
        await self.wait(self.lifetime_check_interval)

        while not self.is_stopped():
            for lifetime in list(self.lifetimes.values()):
                # TODO retry the lifetime in a bit...
                if lifetime.is_stopped():
                    continue

                if not lifetime.is_healthy():
                    lifetime.client.logger.warning(f"Client lifetime unhealthy - restarting")
                    await self.restart_lifetime(lifetime.client)
                    continue

                if self.instance.connection.is_connected() and not lifetime.client.connected:
                    lifetime.client.logger.warning(
                        f"Instance is connected but client has not received connected event yet.")

            await self.wait(self.lifetime_check_interval)

        self.logger.info("Lifetime manager loop stopped - stopping all lifetimes")

        for _, lifetime in list(self.lifetimes.values()):
            lifetime.stop()

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

    async def restart_lifetime(self, client: Client) -> None:
        await self.stop_lifetime(client)
        await self.start_lifetime(client)

    def remove(self, client: Client) -> None:
        lifetime = self.lifetimes.pop(client.config.unique_id, None)

        if lifetime is not None:
            lifetime.stop()
