from .app import ClientMode, ClientOptions
from .cli import ClientCli
from .config import ConfigManagerType
from .examples.virtual.virtual_client import VirtualClient
from .examples.virtual.virtual_config import VirtualConfig

if __name__ == '__main__':
    options = ClientOptions()
    options.mode = ClientMode.SINGLE
    options.config_manager_type = ConfigManagerType.MEMORY
    options.client_t = VirtualClient
    options.config_t = VirtualConfig

    cli = ClientCli(options)
    cli(prog_name="python -m simplyprint_ws_client")
