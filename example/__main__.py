from simplyprint_ws_client import ClientApp, ConfigManagerType, ClientSettings, ConnectionMode
from simplyprint_ws_client.shared.cli.cli import ClientCli
from simplyprint_ws_client.shared.logging import setup_logging
from .virtual_client import VirtualClient, VirtualConfig, VirtualCamera

if __name__ == "__main__":
    settings = ClientSettings(
        name="VirtualPrinters",
        mode=ConnectionMode.MULTI,
        client_factory=VirtualClient,
        config_factory=VirtualConfig,
        allow_setup=True,
        config_manager_t=ConfigManagerType.JSON,
        development=True,
        camera_workers=1,
        camera_protocols=[VirtualCamera],
    )

    setup_logging(settings)
    app = ClientApp(settings)
    cli = ClientCli(app)
    cli.start_client = lambda: app.run_blocking()
    cli(prog_name="python -m simplyprint_ws_client")