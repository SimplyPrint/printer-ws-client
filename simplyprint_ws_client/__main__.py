from simplyprint_ws_client.client.app import ClientMode, ClientOptions
from .cli import ClientCli
from simplyprint_ws_client.client.config import ConfigManagerType
from .examples.virtual.virtual_client import VirtualClient
from .examples.virtual.virtual_config import VirtualConfig

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
