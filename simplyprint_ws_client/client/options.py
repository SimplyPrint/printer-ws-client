from enum import Enum
from typing import NamedTuple, Type, Callable
from typing import Optional

from .client import Client
from .config import Config
from .config import ConfigManagerType
from .instance import Instance, MultiPrinter, SinglePrinter
from ..const import SimplyPrintBackend


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
    backend: Optional[SimplyPrintBackend] = None
    development: bool = False

    # Client name and version used for various purposes.
    name: Optional[str] = "printers"
    version: Optional[str] = "0.1"

    config_manager_type: ConfigManagerType = ConfigManagerType.MEMORY

    client_t: Optional[TConfigFactory] = None
    config_t: Optional[Type[Config]] = None

    allow_setup: bool = False
    cache_clients: bool = False  # Cache clients between restarts, important if state is re-source able.
    reconnect_timeout = 5.0
    tick_rate = 1.0

    # Sentry DSN for sentry logging.
    sentry_dsn: Optional[str] = None

    def is_valid(self) -> bool:
        return self.client_t is not None and self.config_t is not None
