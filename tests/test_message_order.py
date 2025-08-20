import pytest

from simplyprint_ws_client import (
    Client,
    PrinterConfig,
    PrinterStatus,
    JobInfoMsg,
    StateChangeMsg,
)


@pytest.fixture
def client():
    client = Client(PrinterConfig.get_new())
    client.config.id = 1
    client.config.in_setup = False
    return client


def test_message_order_simple(client):
    msgs, _ = client.consume()
    assert len(msgs) == 0

    client.printer.job_info.started = True
    client.printer.status = PrinterStatus.PRINTING

    # Assert the order of messages
    msgs, _ = client.consume()
    assert len(msgs) == 2
    assert msgs[0].__class__ == JobInfoMsg
    assert msgs[1].__class__ == StateChangeMsg
