import pytest

from simplyprint_ws_client import (
    ClientSettings,
    DefaultClient,
    PrinterConfig,
    ClientApp,
)


@pytest.fixture
def app():
    settings = ClientSettings(
        DefaultClient,
        PrinterConfig,
        camera_workers=0,
    )

    app = ClientApp(settings)
    app.run_detached()
    yield app
    app.stop()


def test_virtual_client(app: ClientApp):
    config = PrinterConfig.get_new()
    client = app.add(config)
    app.wait(2)
    assert client.config.short_id is not None


def test_single_connection_active_flag(app: ClientApp):
    config = PrinterConfig.get_new()
    client = app.add(config)
    app.wait(2)
    assert client.config.short_id is not None
    assert client.is_added(), "Client should be added after being activated."

    client.active = False
    app.wait(2)
    assert not client.is_added(), "Client should be removed after being deactivated."

    client.active = True
    app.wait(2)
    assert client.is_added(), "Client should be added after being re-activated."
