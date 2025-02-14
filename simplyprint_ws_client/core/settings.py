__all__ = ["ClientSettings", "ClientFactory"]

from dataclasses import dataclass
from typing import Optional, Type, Union, Callable, Protocol, TypeVar, List

from .client import Client
from .config import ConfigManagerType, PrinterConfig
from .ws_protocol.connection import ConnectionMode
from ..shared.asyncio.event_loop_runner import EventLoopBackend
from ..shared.camera.base import BaseCameraProtocol
from ..shared.sp.url_builder import SimplyPrintBackend

TAnyClient = TypeVar("TAnyClient", bound=Client)
TAnyPrinterConfig = TypeVar("TAnyPrinterConfig", bound=PrinterConfig)


class ClientFactory(Protocol):
    def __call__(self, config: TAnyPrinterConfig, *args, **kwargs) -> TAnyClient:
        ...


TClientFactory = Union[Type[TAnyClient], ClientFactory]
TConfigFactory = Union[Type[TAnyPrinterConfig], Callable[..., TAnyPrinterConfig]]


@dataclass
class ClientSettings:
    client_factory: Optional[TClientFactory] = None
    config_factory: Optional[TConfigFactory] = None
    name: Optional[str] = "printers"
    version: Optional[str] = "0.1"
    mode: ConnectionMode = ConnectionMode.SINGLE
    backend: Optional[SimplyPrintBackend] = None
    event_loop_backend: EventLoopBackend = EventLoopBackend.ASYNCIO
    development: bool = False
    config_manager_t: ConfigManagerType = ConfigManagerType.MEMORY
    allow_setup: bool = True
    tick_rate = 1.0
    reconnect_timeout = 5.0
    sentry_dsn: Optional[str] = None
    camera_workers: Optional[int] = None
    camera_protocols: Optional[List[Type[BaseCameraProtocol]]] = None

    def new_config_manager(self):
        return self.config_manager_t(name=self.name, config_t=self.config_factory)
