import asyncio
import functools
import logging
import threading
from asyncio import Future
from contextlib import suppress
from typing import Optional, Generic, Dict

from .config import ConfigManager, PrinterConfig
from .factory import ClientFactory
from .instance import Instance
from .instance.instance import TClient, TConfig
from .options import ClientOptions
from .provider import ClientProvider, BasicClientProvider, TClientProviderFactory
from ..const import APP_DIRS
from ..helpers.sentry import Sentry
from ..helpers.url_builder import SimplyPrintURL
from ..utils import traceability
from ..utils.event_loop_runner import EventLoopRunner


class ClientApp(Generic[TClient, TConfig]):
    options: ClientOptions

    logger = logging.getLogger("simplyprint.client_app")
    instance: Instance[TClient, TConfig]
    instance_thread: Optional[threading.Thread] = None

    config_manager: ConfigManager[PrinterConfig]
    client_providers: Dict[TConfig, ClientProvider]
    provider_factory: TClientProviderFactory

    def __init__(self, options: ClientOptions, provider_factory: Optional[TClientProviderFactory] = None) -> None:
        if not options.is_valid():
            raise ValueError("Invalid options")

        self.options = options

        # Set correct simplyprint version
        if options.backend:
            SimplyPrintURL.set_backend(options.backend)

        self.instance = options.create_instance()
        self.config_manager = self.instance.config_manager

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

    def load(self, config: PrinterConfig) -> Optional[Future]:
        # Lock to ensure that we don't load the same config twice
        if not self.config_manager.contains(config):
            self.config_manager.persist(config)
            self.config_manager.flush()

        if config in self.client_providers:
            provider = self.client_providers.get(config)
        else:
            try:
                provider = self.provider_factory(config=config)
            except Exception as e:
                self.logger.error(f"Failed to create provider for {config}", exc_info=e)
                return

            self.client_providers[config] = provider

        task = provider.ensure()
        fut = asyncio.run_coroutine_threadsafe(task, self.instance.event_loop)

        try:
            return asyncio.wrap_future(fut, loop=asyncio.get_running_loop())
        except RuntimeError:
            return fut

    def unload(self, config: PrinterConfig) -> Optional[Future]:
        provider = self.client_providers.get(config)

        if not provider:
            self.logger.warning(
                f"Could not unload provider as provider for {config.unique_id} not found.")
            return

        self.client_providers.pop(config)

        async def _unload():
            await provider.ensure(remove=True)
            await provider.delete()

        task = _unload()
        fut = asyncio.run_coroutine_threadsafe(task, self.instance.event_loop)

        try:
            return asyncio.wrap_future(fut, loop=asyncio.get_running_loop())
        except RuntimeError:
            return fut

    def get_provider(self, config: PrinterConfig):
        return self.client_providers.get(config)

    async def run(self):
        async def _register_configs():
            configs = self.config_manager.get_all()
            load_tasks = []

            for config in configs:
                load_tasks.append(self.load(config))

            await asyncio.gather(*[t for t in load_tasks if t is not None], return_exceptions=True)

        with suppress(asyncio.CancelledError):
            async with self.instance:
                # Register all clients this has to be non-blocking
                # so that instance run can start polling events as we wait
                # to get the connected message before we can start sending events.
                # SAFETY: This is potentially unsafe depending on the given provider implementation.
                _ = self.instance.event_loop.create_task(_register_configs())

                await self.instance.run()

        self.logger.debug("Client instance has stopped")

    def run_blocking(self, debug=False, contexts=None):
        contexts = [] if contexts is None else contexts

        contexts.append(functools.partial(traceability.enable_traceable, debug))

        with EventLoopRunner(debug, contexts, self.options.event_loop_backend) as runner:
            runner.run(self.run())

    def run_detached(self, *args, **kwargs):
        """ Run the client in a separate thread. """
        if self.instance_thread:
            self.logger.warning("Client instance already running - stopping old instance")
            self.stop()

        self.instance_thread = threading.Thread(target=self.run_blocking, args=args, kwargs=kwargs)
        self.instance_thread.start()

    def stop(self):
        # Cleanup all providers before stopping the instance
        # as the event loop is not available after stopping the instance.
        for config in list(self.client_providers.keys()):
            self.unload(config)

        self.instance.stop()

        # If the instance is running in a separate thread, wait for it to stop
        if self.instance_thread:
            self.instance_thread.join()
            self.instance_thread = None
