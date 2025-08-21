"""Test active_tool state changes -> ToolMsg flow."""

from simplyprint_ws_client import Client, ToolMsg


def test_active_tool_change(client: Client):
    changeset = client.printer.model_recursive_changeset
    assert changeset == {}

    # Change active tool
    client.printer.active_tool = 1
    client.printer.tool0.active_material = 1010

    messages, _ = client.consume()

    assert len(messages) == 1

    message = messages[0]

    assert message.__class__ == ToolMsg
    assert message.data == {"new": 1}

    message.reset_changes(client.printer)

    changeset = client.printer.model_recursive_changeset
    assert changeset == {}
