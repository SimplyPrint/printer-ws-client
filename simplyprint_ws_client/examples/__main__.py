import logging

from simplyprint_ws_client.cli import ClientCli
from simplyprint_ws_client.client import ClientApp, ClientOptions, ClientMode
from simplyprint_ws_client.client.config import ConfigManagerType
from simplyprint_ws_client.client.logging import ClientHandler
from simplyprint_ws_client.examples.virtual_client import VirtualClient, VirtualConfig
from simplyprint_ws_client.helpers.url_builder import SimplyPrintBackend

if __name__ == "__main__":
    client_options = ClientOptions(
        name="VirtualClient",
        mode=ClientMode.MULTI_PRINTER,
        client_t=VirtualClient,
        config_t=VirtualConfig,
        allow_setup=True,
        config_manager_type=ConfigManagerType.JSON,
        backend=SimplyPrintBackend.TESTING,
    )

    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s %(name)s.%(funcName)s: %(message)s",
        handlers=[logging.StreamHandler(), ClientHandler.root_handler(client_options)]
    )

    app = ClientApp(client_options)
    cli = ClientCli(app)
    cli.start_client = lambda: app.run_blocking()
    cli(prog_name="python -m simplyprint_ws_client")
