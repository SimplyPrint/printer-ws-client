import asyncio
import logging
import threading
from typing import Callable, Optional, Type, Generic, Union

from .cache import ClientCache
from .client import Client
from .config import Config, ConfigManager
from .instance import Instance
from .instance.instance import InstanceException, TClient, TConfig
from .instance.multi_printer import MultiPrinterException
from .options import ClientOptions
from ..const import APP_DIRS
from ..helpers.sentry import Sentry
from ..helpers.url_builder import SimplyPrintUrl
from ..utils.event_loop_runner import EventLoopRunner


class ClientFactory:
    options: ClientOptions
    client_t: Optional[Union[Type[Client], Callable[[], Client]]] = None
    config_t: Optional[Type[Config]] = None

    def __init__(self, options: ClientOptions, client_t: Optional[Type[Client]] = None,
                 config_t: Optional[Type[Config]] = None) -> None:
        self.options = options
        self.client_t = client_t
        self.config_t = config_t

    def create_client(self, *args, config: Optional[Config] = None, **kwargs) -> Client:
        return self.client_t(*args, config=config or self.config_t.get_blank(), **kwargs)


class ClientApp(Generic[TClient, TConfig]):
    options: ClientOptions

    logger = logging.getLogger("simplyprint.client_app")
    instance: Instance[TClient, TConfig]
    instance_thread: Optional[threading.Thread] = None

    config_manager: ConfigManager
    client_factory: ClientFactory
    client_cache: Optional[ClientCache] = None

    def __init__(self, options: ClientOptions) -> None:
        if not options.is_valid():
            raise ValueError("Invalid options")

        self.options = options

        # Set correct simplyprint version
        if options.backend:
            SimplyPrintUrl.set_current(options.backend)

        config_manager_class = options.config_manager_type.get_class()
        instance_class = options.mode.get_class()

        self.config_manager = config_manager_class(name=options.name, config_t=options.config_t)
        self.instance = instance_class(config_manager=self.config_manager,
                                       allow_setup=options.allow_setup, reconnect_timeout=options.reconnect_timeout, )

        self.client_factory = ClientFactory(
            options=options,
            client_t=options.client_t,
            config_t=options.config_t
        )

        self.client_cache = ClientCache() if options.cache_clients else None

        log_file = APP_DIRS.user_log_path / f"{options.name}.log"

        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True)

        if options.sentry_dsn:
            Sentry.initialize_sentry(self.options)

    async def run(self):
        async with self.instance:
            # Register all clients
            for config in self.config_manager.get_all():
                client = None

                self.logger.debug(f"Registering client {config}")

                if self.client_cache:
                    client = self.client_cache.by_other(config)

                if not client:
                    client = self.create_client(config)

                try:
                    await self.instance.register_client(client)
                except MultiPrinterException as e:
                    self.logger.error(f"Failed to register client: {e}")
                except InstanceException as e:
                    self.logger.error(f"Failed to register client {config}: {e}")

            await self.instance.run()

        self.logger.debug("Client instance has stopped")

    def create_client(self, config: Optional[Config]):
        client = self.client_factory.create_client(config=config, event_loop_provider=self.instance)

        if self.client_cache:
            self.client_cache.add(client)

        return client

    async def _register_client(self, client: Client):
        try:
            await self.instance.register_client(client)
        except InstanceException:
            pass

    async def _reload_client(self, client: Client):
        await self.instance.deregister_client(client)
        new_client = self.create_client(client.config)
        await self._register_client(new_client)

    def delete_client(self, client: Client) -> asyncio.Future:
        if self.client_cache:
            self.client_cache.remove(client)

        return asyncio.run_coroutine_threadsafe(self.instance.deregister_client(client, remove_from_config=True),
                                                self.instance.event_loop)

    def register_client(self, client: Client) -> asyncio.Future:
        return asyncio.run_coroutine_threadsafe(self._register_client(client), self.instance.event_loop)

    def add_new_client(self, config: Optional[Config]) -> asyncio.Future:
        new_client = self.create_client(config)
        return self.register_client(new_client)

    def reload_client(self, client: Client) -> asyncio.Future:
        return asyncio.run_coroutine_threadsafe(self._reload_client(client), self.instance.event_loop)

    def run_blocking(self):
        with EventLoopRunner() as runner:
            runner.run(self.run())

    def run_detached(self):
        """ Run the client in a separate thread. """
        if self.instance_thread:
            self.logger.warning("Client instance already running - stopping old instance")
            self.stop()

        self.instance_thread = threading.Thread(target=self.run_blocking)
        self.instance_thread.start()

    def stop(self):
        # Cleanup cache before stopping
        if self.client_cache:
            self.client_cache.sync(self.instance)

        self.instance.stop()

        # If the instance is running in a separate thread, wait for it to stop
        if self.instance_thread:
            self.instance_thread.join()
            self.instance_thread = None
