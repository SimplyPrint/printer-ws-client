import asyncio
import functools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Protocol, Generic, TypeVar

from .instance.instance import InstanceException
from ..utils.event_loop_provider import EventLoopProvider

if TYPE_CHECKING:
    from .config import Config
    from .app import ClientApp
    from .client import Client
    from .factory import ClientFactory


class TClientProviderFactory(Protocol):
    def __call__(self, config: 'Config') -> 'ClientProvider':
        ...


TConfig = TypeVar('TConfig', bound='Config')


class ClientProvider(ABC, Generic[TConfig], EventLoopProvider[asyncio.AbstractEventLoop]):
    """
    Instead of a pure factory, write a custom provider that
    decides when to add or remove the config from the instance.

    Wraps a config and provides the client. Is allowed to return None
    to indicate it should not be added.
    """

    app: 'ClientApp'
    factory: 'ClientFactory'
    config: TConfig

    def __init__(self, app: 'ClientApp', factory: 'ClientFactory', config: TConfig):
        super().__init__(provider=app.instance)
        self.app = app
        self.factory = factory
        self.config = config

    async def ensure(self, remove=False):
        client = self.get_client()

        # Deregister client if not supposed to be provided.
        if client is None:
            client = self.app.instance.get_client(self.config)
            remove = True

        has_client = self.app.instance.has_client(client)

        self.app.instance.logger.debug(f"Loading provider {self.config} {bool(client)=} {remove=} {has_client=}")

        if has_client and remove:
            await self.app.instance.deregister_client(client)
            return

        if client is not None and not has_client and not remove:
            # Add the client to the instance.
            try:
                await self.app.instance.register_client(client)
            except InstanceException as e:
                self.app.instance.logger.error(f"Failed to register client: {e}")

    @abstractmethod
    def get_client(self) -> Optional['Client']:
        ...

    @classmethod
    def get_factory(cls, *args, **kwargs) -> TClientProviderFactory:
        return functools.partial(cls, *args, **kwargs)


class BasicClientProvider(ClientProvider):
    is_cached: bool = False

    _cached_client: Optional['Client'] = None

    def __init__(self, *args, is_cached=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_cached = is_cached

    def get_client(self) -> 'Client':
        if self.is_cached and self._cached_client:
            return self._cached_client

        client = self.factory.create_client(config=self.config, event_loop_provider=self.app.instance)

        if self.is_cached:
            self._cached_client = client

        return client
