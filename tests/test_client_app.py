from simplyprint_ws_client import (
    ClientSettings,
    DefaultClient,
    PrinterConfig,
    ClientApp,
)


def test_virtual_client():
    client_settings = ClientSettings(
        DefaultClient,
        PrinterConfig,
        camera_workers=0,
    )

    config = PrinterConfig.get_new()

    client_app = ClientApp(client_settings)

    client = client_app.add(config)

    client_app.run_detached()
    client_app.wait(2)

    assert client.config.short_id is not None

    client_app.stop()
