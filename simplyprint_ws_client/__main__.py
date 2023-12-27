from .app import ClientMode, ClientOptions
from .cli import ClientCli
from .config import ConfigManagerType
from .examples.virtual.virtual_client import VirtualClient
from .examples.virtual.virtual_config import VirtualConfig

if __name__ == '__main__':
    options = ClientOptions(
        mode=ClientMode.MULTIPRINTER,
        name="VirtualClient",
        config_manager_type=ConfigManagerType.JSON,
        client_t=VirtualClient,
        config_t=VirtualConfig,
        allow_setup=True
    )

    cli = ClientCli(options)
    cli(prog_name="python -m simplyprint_ws_client")
