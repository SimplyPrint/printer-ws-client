import logging
import time

from simplyprint_ws_client.cli import ClientCli
from simplyprint_ws_client.client import ClientApp, ClientOptions, ClientMode
from simplyprint_ws_client.client.config import ConfigManagerType
from simplyprint_ws_client.client.logging import ClientHandler
from simplyprint_ws_client.examples.virtual_client import VirtualClient, VirtualConfig
from simplyprint_ws_client.helpers.url_builder import SimplyPrintBackend


def start_client(app: ClientApp):
    app.run_detached()

    try:
        while True:
            time.sleep(10)
            ...
    finally:
        app.stop()


if __name__ == "__main__":
    client_options = ClientOptions(
        name="VirtualPrinters",
        mode=ClientMode.MULTI_PRINTER,
        client_t=VirtualClient,
        config_t=VirtualConfig,
        allow_setup=True,
        config_manager_type=ConfigManagerType.JSON,
        backend=SimplyPrintBackend.TESTING
    )

    client_app = ClientApp(client_options)
    client_cli = ClientCli(client_app)
    client_cli.start_client = start_client

    logging.basicConfig(
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s %(name)s.%(funcName)s: %(message)s",
        handlers=[logging.StreamHandler(), ClientHandler.root_handler(client_options)]
    )

    client_cli()
