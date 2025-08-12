"""Test active_tool state changes -> ToolMsg flow."""

import weakref
from unittest import TestCase

from simplyprint_ws_client import PrinterConfig, Client, ToolMsg


class TestActiveTool(TestCase):
    def setUp(self):
        self.client = Client(PrinterConfig.get_new())
        self.client.config.id = 1
        self.client.config.in_setup = False
        self.ctx = weakref.ref(self.client)

    def test_active_tool_change(self):
        changeset = self.client.printer.model_recursive_changeset
        self.assertDictEqual(changeset, {})

        # Change active tool
        self.client.printer.active_tool = 1

        messages, _ = self.client.consume()

        self.assertEqual(len(messages), 1)

        message = messages[0]

        self.assertEqual(message.__class__, ToolMsg)
        self.assertDictEqual(message.data, {"new": 1})

        message.reset_changes(self.client.printer)

        changeset = self.client.printer.model_recursive_changeset
        self.assertDictEqual(changeset, {})
