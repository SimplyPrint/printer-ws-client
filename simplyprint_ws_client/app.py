import asyncio
import logging
from asyncio import AbstractEventLoop
from enum import Enum
from typing import Callable, NamedTuple, Optional, Type

from .client import Client
from .config import Config, ConfigManager, ConfigManagerType
from .const import APP_DIRS, SimplyPrintUrl, SimplyPrintVersion
from .instance import Instance, MultiPrinter, SinglePrinter


class ClientMode(Enum):
    MULTI_PRINTER = "mp"
    SINGLE = "p"

    def get_class(self) -> Type[Instance]:
        if self == ClientMode.MULTI_PRINTER:
            return MultiPrinter
        elif self == ClientMode.SINGLE:
            return SinglePrinter
        else:
            raise ValueError("Invalid ClientMode")


TConfigFactory = Type[Client] | Callable[..., Client]


class ClientOptions(NamedTuple):
    mode: ClientMode = ClientMode.SINGLE
    backend: Optional[SimplyPrintVersion] = None

    name: Optional[str] = "printers"
    config_manager_type: ConfigManagerType = ConfigManagerType.MEMORY

    client_t: Optional[TConfigFactory] = None
    config_t: Optional[Type[Config]] = None

    allow_setup: bool = False
    reconnect_timeout = 5.0
    tick_rate = 1.0

    def is_valid(self) -> bool:
        return self.client_t is not None and self.config_t is not None


class ClientFactory:
    client_t: Optional[Type[Client] | Callable[..., Client]] = None
    config_t: Optional[Type[Config]] = None

    def __init__(self, client_t: Optional[Type[Client]] = None, config_t: Optional[Type[Config]] = None) -> None:
        self.client_t = client_t
        self.config_t = config_t

    def create_client(self, *args, config: Optional[Config] = None, **kwargs) -> Client:
        return self.client_t(*args, config=config or self.config_t.get_blank(), **kwargs)


class ClientApp:
    loop: AbstractEventLoop

    logger = logging.getLogger("simplyprint.client_app")
    instance: Instance[Client, Config]

    client_factory: ClientFactory
    config_manager: ConfigManager

    def __init__(self, loop: AbstractEventLoop, options: ClientOptions) -> None:
        if not options.is_valid():
            raise ValueError("Invalid options")

        self.loop = loop

        # Set correct simplyprint version
        if options.backend:
            SimplyPrintUrl.set_current(options.backend)

        config_manager_class = options.config_manager_type.get_class()
        instance_class = options.mode.get_class()

        self.config_manager = config_manager_class(name=options.name, config_t=options.config_t)
        self.instance = instance_class(loop=self.loop, config_manager=self.config_manager,
                                       allow_setup=options.allow_setup, reconnect_timeout=options.reconnect_timeout,
                                       tick_rate=options.tick_rate)
        self.client_factory = ClientFactory(client_t=options.client_t, config_t=options.config_t)

        log_file = APP_DIRS.user_log_path / f"{options.name}.log"

        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True)

        # handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, backupCount=5)
        # logging.basicConfig()

        self.loop.set_exception_handler(self.exception_handler)

    def exception_handler(self, loop, context):
        self.logger.exception("Unhandled exception in async loop.", exc_info=context.get("exception"))

    async def run(self):
        # Register all clients
        for config in self.config_manager.get_all():
            self.logger.debug(f"Registering client {config}")

            client = self.client_factory.create_client(config=config)
            await self.instance.register_client(client)

        await self.instance.run()

        self.logger.debug("Client instance has stopped")

    async def _delete_client(self, client: Client):
        await self.instance.delete_client(client)

    async def _add_new_client(self, config: Optional[Config]):
        client = self.client_factory.create_client(config=config)
        await self.instance.register_client(client)

    async def _reload_client(self, client: Client):
        await self._delete_client(client)
        await self._add_new_client(client.config)

    def delete_client(self, client: Client):
        asyncio.run_coroutine_threadsafe(self._delete_client(client), self.loop)

    def add_new_client(self, config: Optional[Config]):
        asyncio.run_coroutine_threadsafe(self._add_new_client(config), self.loop)

    def reload_client(self, client: Client):
        asyncio.run_coroutine_threadsafe(self._reload_client(client), self.loop)

    def start(self):
        self.loop.create_task(self.run())
        self.loop.run_forever()

    def stop(self):
        self.instance.stop()
