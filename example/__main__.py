from simplyprint_ws_client.core.app import ClientApp
from simplyprint_ws_client.core.config import ConfigManagerType
from simplyprint_ws_client.core.settings import ClientSettings
from simplyprint_ws_client.core.ws_protocol.connection import ConnectionMode
from simplyprint_ws_client.shared.cli.cli import ClientCli
from simplyprint_ws_client.shared.logging import ClientHandler
from simplyprint_ws_client.shared.sp.url_builder import SimplyPrintBackend
from .virtual_client import VirtualClient, VirtualConfig

if __name__ == "__main__":
    settings = ClientSettings(
        name="VirtualPrinters",
        mode=ConnectionMode.MULTI,
        client_factory=VirtualClient,
        config_factory=VirtualConfig,
        allow_setup=True,
        config_manager_t=ConfigManagerType.JSON,
    )

    ClientHandler.setup_logging(settings)
    app = ClientApp(settings)
    cli = ClientCli(app)
    cli.start_client = lambda: app.run_blocking()
    cli(prog_name="python -m simplyprint_ws_client")
