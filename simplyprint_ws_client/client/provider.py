import asyncio
import functools
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Protocol, Generic, TypeVar

from .instance.instance import InstanceException
from .instance.multi_printer import MultiPrinterFailedToAddException
from ..utils.event_loop_provider import EventLoopProvider
from ..utils.stoppable import AsyncStoppable

if TYPE_CHECKING:
    from .config import Config
    from .app import ClientApp
    from .client import Client
    from .factory import ClientFactory


class TClientProviderFactory(Protocol):
    def __call__(self, config: 'Config') -> 'ClientProvider':
        ...


TConfig = TypeVar('TConfig', bound='Config')


class ClientProvider(Generic[TConfig], AsyncStoppable, EventLoopProvider[asyncio.AbstractEventLoop], ABC):
    """
    Instead of a pure factory, write a custom provider that
    decides when to add or remove the config from the instance.

    Wraps a config and provides the client. Is allowed to return None
    to indicate it should not be added.
    """

    __ensure_lock: asyncio.Lock
    __retry_task: Optional[asyncio.Task] = None

    app: 'ClientApp'
    factory: 'ClientFactory'
    config: TConfig

    def __init__(self, app: 'ClientApp', factory: 'ClientFactory', config: TConfig):
        AsyncStoppable.__init__(self)
        EventLoopProvider.__init__(self, provider=app.instance)

        self.__ensure_lock = asyncio.Lock()

        self.app = app
        self.factory = factory
        self.config = config

    async def _retry(self, timeout: float, attempts: Optional[int] = 3):
        await self.app.instance.wait(timeout)

        try:
            self.app.instance.logger.debug(f"Retrying ensure for {self.config.unique_id}")
            await self.ensure()
        except Exception as e:
            self.app.instance.logger.error(f"Failed to retry ensure: {e} {attempts=}")

            if attempts is None or attempts > 0:
                await self._retry(timeout=timeout, attempts=attempts - 1 if attempts is not None else None)
                return

        self.__retry_task = None

    async def _ensure_retry_task(self, timeout=10.0):
        """The retry task will loop for N attempts until it is successful, after the first failed attempt to add
        itself."""
        if self.__retry_task is not None:
            return None

        # SAFETY: This is potentially unsafe depending on the provider implementation.
        self.__retry_task = asyncio.create_task(self._retry(timeout=timeout))

    async def _cancel_retry_task(self):
        """Used when we want to explicitly cancel the retry task."""
        if self.__retry_task is not None:
            self.__retry_task.cancel()
            self.__retry_task = None

    async def delete(self):
        """Called when the provider is deleted."""
        if self.is_stopped():
            raise RuntimeError("Provider is already stopped")

        self.stop()

        await self._cancel_retry_task()

    async def ensure(self, remove=False):
        _remove = remove

        async with self.__ensure_lock:
            client = self.get_client()
            # Deregister client if not supposed to be provided.
            if client is None:
                client = self.app.instance.get_client(self.config)
                _remove = True

            has_client = self.app.instance.has_client(client)

            self.app.instance.logger.debug(
                f"Loading provider {self.config.unique_id} {bool(client)=} {remove=} {_remove=} {has_client=}")

            # If we trigger ensure with explicit remove we need to cancel the retry task.
            # We are never currently running inside the retry task as the retry task is never
            # called with explicit remove.
            if remove:
                await self._cancel_retry_task()

            # Automatically remove client if it is not supposed to be provided.
            # It is up to the implementation to trigger ensure again.
            if _remove and has_client:
                try:
                    await self.app.instance.deregister_client(client)
                except InstanceException as e:
                    self.app.instance.logger.warning(f"Failed to deregister client: %s", str(e))

                return

            if _remove:
                return

            if client is not None and not has_client:
                # Add the client to the instance.
                try:
                    await self.app.instance.register_client(client)

                except MultiPrinterFailedToAddException:
                    # The configuration is not valid.
                    self.app.instance.logger.error(
                        f"Failed to add client {client.config.id} to instance due to response status false.")
                    raise
                except InstanceException as e:
                    self.app.instance.logger.error(f"Failed to register client %s", str(e))
                    await self._ensure_retry_task()
                except Exception as e:
                    self.app.instance.logger.error(f"An exception occurred while registering the client", exc_info=e)
                    raise

    @abstractmethod
    def get_client(self) -> Optional['Client']:
        ...

    @classmethod
    def get_factory(cls, *args, **kwargs) -> TClientProviderFactory:
        return functools.partial(cls, *args, **kwargs)


class BasicClientProvider(ClientProvider[TConfig]):
    is_cached: bool = False

    _cached_client: Optional['Client'] = None

    def __init__(self, *args, is_cached=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_cached = is_cached

    def get_client(self) -> Optional['Client']:
        if self.is_stopped():
            return None

        if self.is_cached and self._cached_client:
            return self._cached_client

        client = self.factory.create_client(config=self.config, event_loop_provider=self.app.instance)

        if self.is_cached:
            self._cached_client = client

        return client
