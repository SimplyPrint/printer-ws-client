"""Test active_tool state changes -> ToolMsg flow."""

import pytest

from simplyprint_ws_client import PrinterConfig, Client, ToolMsg


@pytest.fixture
def client():
    client = Client(PrinterConfig.get_new())
    client.config.id = 1
    client.config.in_setup = False
    return client


def test_active_tool_change(client):
    changeset = client.printer.model_recursive_changeset
    assert changeset == {}

    # Change active tool
    client.printer.active_tool = 1

    messages, _ = client.consume()

    assert len(messages) == 1

    message = messages[0]

    assert message.__class__ == ToolMsg
    assert message.data == {"new": 1}

    message.reset_changes(client.printer)

    changeset = client.printer.model_recursive_changeset
    assert changeset == {}
