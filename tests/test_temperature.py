"""Test Temperature state + index based state producer rules with * as index."""

import weakref
from unittest import TestCase

from simplyprint_ws_client import PrinterConfig, Client, TemperatureMsg


class TestTemperature(TestCase):
    def setUp(self):
        self.client = Client(PrinterConfig.get_new())
        self.client.config.id = 1
        self.client.config.in_setup = False
        self.ctx = weakref.ref(self.client)

    def test_tool0_temperature(self):
        tool0 = self.client.printer.tool0

        changeset = self.client.printer.model_recursive_changeset

        self.assertDictEqual(changeset, {})

        tool0.temperature.actual = 200
        tool0.temperature.target = 250

        messages, _ = self.client.consume()

        self.assertEqual(len(messages), 1)

        message = messages[0]

        self.assertEqual(message.__class__, TemperatureMsg)
        self.assertDictEqual(message.data, {"tool0": [200, 250]})

        message.reset_changes(self.client.printer)

        changeset = self.client.printer.model_recursive_changeset

        self.assertDictEqual(changeset, {})

        tool0.temperature.actual = 250
        self.client.printer.bed.temperature.target = 60

        messages, _ = self.client.consume()

        self.assertEqual(len(messages), 1)

        message = messages[0]

        self.assertEqual(message.__class__, TemperatureMsg)
        self.assertDictEqual(message.data, {"tool0": [250, 250], "bed": [None, 60]})

        message.reset_changes(self.client.printer)

        changeset = self.client.printer.model_recursive_changeset

        self.assertDictEqual(changeset, {})

    def test_multiple_tools_temperatures(self):
        self.client.printer.tool_count = 2
        tool0 = self.client.printer.tools[0]
        tool1 = self.client.printer.tools[1]

        changeset = self.client.printer.model_recursive_changeset
        self.assertDictEqual(changeset, {})

        tool0.temperature.actual = 200
        tool0.temperature.target = 250
        tool1.temperature.actual = 180
        tool1.temperature.target = 220

        messages, _ = self.client.consume()

        self.assertEqual(len(messages), 1)
        message = messages[0]

        self.assertEqual(message.__class__, TemperatureMsg)

        self.assertDictEqual(message.data, {"tool0": [200, 250], "tool1": [180, 220]})
