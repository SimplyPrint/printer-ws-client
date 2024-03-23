from typing import Optional, Dict

from .client import Client
from .config import Config
from .instance import Instance
from .instance.instance import TClient, TConfig


class ClientCache:
    """ Caches clients to optimize re-addition of clients."""

    clients: Dict[str, Client]

    def __init__(self):
        self.clients = {}

    def add(self, client: Client):
        self.clients[client.config.unique_id] = client

    def remove(self, client: Client):
        self.clients.pop(client.config.unique_id, None)

    def sync(self, instance: Instance[TClient, TConfig]):
        """ Ensure clients removed between start and stop are removed from the cache."""

        for client in self.clients.values():
            if not instance.has_client(client):
                self.remove(client)

    def by_other(self, config: Config) -> Optional[Client]:
        for client in self.clients.values():
            if config.partial_eq(client.config):
                return client

        return None
