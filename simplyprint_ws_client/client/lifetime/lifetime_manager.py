from typing import Generic, Dict

from .lifetime import ClientLifetime
from ..instance import TClient
from ...utils.stoppable import SyncStoppable


class LifetimeManager(Generic[TClient], SyncStoppable):
    lifetimes: Dict[TClient, ClientLifetime[TClient]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ...

    def add(self, client: TClient) -> ClientLifetime[TClient]:
        lifetime = ClientLifetime(client, stoppable=self)
        self.lifetimes[client] = lifetime
        return lifetime

    def remove(self, client: TClient) -> None:
        lifetime = self.lifetimes.pop(client, None)

        if lifetime is not None:
            lifetime.stop()
