from enum import Enum
from typing import NamedTuple, Type, Callable, Union
from typing import Optional

from .config import Config
from .config import ConfigManagerType
from .factory import _TClientFactory
from .instance import Instance, MultiPrinter, SinglePrinter
from ..helpers.url_builder import SimplyPrintBackend
from ..utils.event_loop_runner import EventLoopBackend


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


TConfigFactory = Union[Type[Config], Callable[[], Config]]


class ClientOptions(NamedTuple):
    mode: ClientMode = ClientMode.SINGLE
    backend: Optional[SimplyPrintBackend] = None
    # UVLoop is bugged, so we default to asyncio.
    # See issue_118950_patch.py for mere.
    event_loop_backend: EventLoopBackend = EventLoopBackend.ASYNCIO
    development: bool = False

    # Client name and version used for various purposes.
    name: Optional[str] = "printers"
    version: Optional[str] = "0.1"

    config_manager_type: ConfigManagerType = ConfigManagerType.MEMORY

    client_t: Optional[_TClientFactory] = None
    config_t: Optional[TConfigFactory] = None

    allow_setup: bool = False
    cache_clients: bool = False  # Cache clients between restarts, important if state is re-source able.
    reconnect_timeout = 5.0
    tick_rate = 1.0

    # Sentry DSN for sentry logging.
    sentry_dsn: Optional[str] = None

    def is_valid(self) -> bool:
        return self.client_t is not None and self.config_t is not None
