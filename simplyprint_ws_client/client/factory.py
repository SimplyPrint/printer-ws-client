from typing import Optional, Union, Type, TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .client import Client
    from .config import Config
    from .options import ClientOptions


class _TClientFactory(Protocol):
    def __call__(self, config: 'Config', *args, **kwargs) -> 'Client':
        ...


TClientFactory = Union[_TClientFactory, Type['Client']]


class ClientFactory:
    options: 'ClientOptions'
    client_t: Optional[Union[Type['Client'], TClientFactory]] = None
    config_t: Optional[Type['Config']] = None

    def __init__(self, options: 'ClientOptions', client_t: Optional[Type['Client']] = None,
                 config_t: Optional[Type['Config']] = None) -> None:
        self.options = options
        self.client_t = client_t
        self.config_t = config_t

    def create_client(self, *args, config: Optional['Config'] = None, **kwargs) -> 'Client':
        return self.client_t(*args, config=config or self.config_t.get_blank(), **kwargs)
