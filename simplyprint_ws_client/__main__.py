from .cli import ClientCli
from .client import ClientMode, ClientOptions
from .client.config import ConfigManagerType
from .examples.virtual_client import VirtualClient, VirtualConfig

if __name__ == '__main__':
    options = ClientOptions(
        mode=ClientMode.MULTI_PRINTER,
        name="VirtualClient",
        config_manager_type=ConfigManagerType.JSON,
        client_t=VirtualClient,
        config_t=VirtualConfig,
        allow_setup=True
    )

    cli = ClientCli(options)
    cli(prog_name="python -m simplyprint_ws_client")
