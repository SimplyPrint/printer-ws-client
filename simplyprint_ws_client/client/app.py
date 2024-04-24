import asyncio
import functools
import logging
import threading
from typing import Optional, Generic, Dict

from .config import Config, ConfigManager
from .factory import ClientFactory
from .instance import Instance
from .instance.instance import TClient, TConfig
from .options import ClientOptions
from .provider import ClientProvider, BasicClientProvider, TClientProviderFactory
from ..const import APP_DIRS
from ..helpers.sentry import Sentry
from ..helpers.url_builder import SimplyPrintUrl
from ..utils import traceability
from ..utils.event_loop_runner import EventLoopRunner


class ClientApp(Generic[TClient, TConfig]):
    options: ClientOptions

    logger = logging.getLogger("simplyprint.client_app")
    instance: Instance[TClient, TConfig]
    instance_thread: Optional[threading.Thread] = None

    config_manager: ConfigManager
    client_providers: Dict[Config, ClientProvider]
    provider_factory: TClientProviderFactory

    def __init__(self, options: ClientOptions, provider_factory: Optional[TClientProviderFactory] = None) -> None:
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

        self.client_providers = {}

        client_factory = ClientFactory(
            options=options,
            client_t=options.client_t,
            config_t=options.config_t
        )

        if provider_factory:
            self.provider_factory = functools.partial(provider_factory, app=self, factory=client_factory)
        else:
            self.provider_factory = BasicClientProvider.get_factory(app=self,
                                                                    factory=client_factory,
                                                                    is_cached=options.cache_clients)

        log_file = APP_DIRS.user_log_path / f"{options.name}.log"

        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True)

        if options.sentry_dsn:
            Sentry.initialize_sentry(self.options)

    def load(self, config: Config):
        if config in self.client_providers:
            provider = self.client_providers.get(config)
        else:
            provider = self.provider_factory(config=config)
            self.client_providers[config] = provider

        task = provider.ensure()
        asyncio.run_coroutine_threadsafe(task, self.instance.event_loop)
        return task

    def unload(self, config: Config):
        provider = self.client_providers.get(config)

        if not provider:
            return

        del self.client_providers[config]

        task = provider.ensure(remove=True)
        asyncio.run_coroutine_threadsafe(task, self.instance.event_loop)
        return task

    def reload(self, config: Config, create_if_not_exists=False):
        provider = self.client_providers.get(config)

        if not provider:
            if create_if_not_exists:
                self.load(config)

            return

        async def _reload():
            await provider.ensure(remove=True)
            await provider.ensure()

        task = _reload()
        asyncio.run_coroutine_threadsafe(task, self.instance.event_loop)
        return task

    async def run(self):
        async with self.instance:
            # Register all clients
            await asyncio.gather(*[self.load(config) for config in self.config_manager.get_all()],
                                 return_exceptions=True)

            await self.instance.run()

        self.logger.debug("Client instance has stopped")

    def run_blocking(self, enable_tracing=False):
        with EventLoopRunner() as runner:
            with traceability.enable_traceable(enable_tracing):
                runner.run(self.run())

    def run_detached(self, *args, **kwargs):
        """ Run the client in a separate thread. """
        if self.instance_thread:
            self.logger.warning("Client instance already running - stopping old instance")
            self.stop()

        self.instance_thread = threading.Thread(target=self.run_blocking, args=args, kwargs=kwargs)
        self.instance_thread.start()

    def stop(self):
        self.instance.stop()

        # If the instance is running in a separate thread, wait for it to stop
        if self.instance_thread:
            self.instance_thread.join()
            self.instance_thread = None

        # Cleanup all providers
        for provider in list(self.client_providers.keys()):
            del self.client_providers[provider]
