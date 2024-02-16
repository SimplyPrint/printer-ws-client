import asyncio
import logging
from enum import Enum
from typing import Callable, NamedTuple, Optional, Type

from .client import Client
from .config import Config, ConfigManager, ConfigManagerType
from .const import APP_DIRS, SimplyPrintUrl, SimplyPrintVersion
from .instance import Instance, MultiPrinter, SinglePrinter
from .instance.instance import InstanceException
from .instance.multi_printer import MultiPrinterException


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
    options: ClientOptions

    logger = logging.getLogger("simplyprint.client_app")
    instance: Instance[Client, Config]

    client_factory: ClientFactory
    config_manager: ConfigManager

    running_future: asyncio.Future

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
                                       allow_setup=options.allow_setup, reconnect_timeout=options.reconnect_timeout,
                                       tick_rate=options.tick_rate)

        self.client_factory = ClientFactory(client_t=options.client_t, config_t=options.config_t)

        log_file = APP_DIRS.user_log_path / f"{options.name}.log"

        if not log_file.parent.exists():
            log_file.parent.mkdir(parents=True)

        # handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, backupCount=5)
        # logging.basicConfig()

    async def run(self):
        async with self.instance:
            # Register all clients
            for config in self.config_manager.get_all():
                self.logger.debug(f"Registering client {config}")

                client = self.client_factory.create_client(config=config, loop_factory=self.instance.get_loop)

                try:
                    await self.instance.register_client(client)
                except MultiPrinterException as e:
                    self.logger.error(f"Failed to register client: {e}")
                except InstanceException as e:
                    self.logger.error(f"Failed to register client {config}: {e}")

            await self.instance.run()

        self.logger.debug("Client instance has stopped")

    async def _create_new_client(self, config: Optional[Config]):
        client = self.client_factory.create_client(config=config, loop_factory=self.instance.get_loop)

        try:
            await self.instance.register_client(client)
        except InstanceException:
            pass

    async def _reload_client(self, client: Client):
        await self.instance.delete_client(client)
        await self._create_new_client(client.config)

    def delete_client(self, client: Client):
        asyncio.run_coroutine_threadsafe(self.instance.delete_client(client), self.instance.get_loop())

    def remove_client(self, client: Client):
        asyncio.run_coroutine_threadsafe(self.instance.remove_client(client), self.instance.get_loop())

    def add_new_client(self, config: Optional[Config]):
        asyncio.run_coroutine_threadsafe(self._create_new_client(config), self.instance.get_loop())

    def reload_client(self, client: Client):
        asyncio.run_coroutine_threadsafe(self._reload_client(client), self.instance.get_loop())

    def start(self):
        asyncio.run(self.run())

    def stop(self):
        self.instance.stop()
