import unittest

from simplyprint_ws_client.client.protocol.client_events import TemperatureEvent
from simplyprint_ws_client.client.state import PrinterState


class TestTemperatureEvent(unittest.TestCase):
    def test_simple(self):
        state = PrinterState()

        # Defaults to a sentinel value
        self.assertNotEqual(type(state.bed_temperature.target), float)
        self.assertEqual(state.bed_temperature.get_changed(), [])

        state.bed_temperature.actual = 27.21875

        self.assertTrue(state.bed_temperature.has_changed('actual'))
        self.assertFalse(state.bed_temperature.has_changed('target'))

        state.bed_temperature.target = 0.0

        self.assertTrue(state.bed_temperature.has_changed('actual', 'target'))

        diff = TemperatureEvent(TemperatureEvent.build(state))

        self.assertEqual(diff.data, {'bed': [27, 0]})

        # Clear the changes
        diff.on_sent()

        # Empty messages raises an error
        self.assertRaises(ValueError, lambda: TemperatureEvent(TemperatureEvent.build(state)))

        state.tool_temperatures[0].target = 100

        diff = TemperatureEvent(TemperatureEvent.build(state))

        self.assertEqual(diff.data, {'tool0': [0, 100]})
        diff.on_sent()

        state.tool_temperatures[0].actual = 100

        diff = TemperatureEvent(TemperatureEvent.build(state))

        self.assertEqual(diff.data, {'tool0': [100, 100]})
        diff.on_sent()

        state.tool_temperatures[0].target = 0

        diff = TemperatureEvent(TemperatureEvent.build(state))

        self.assertEqual(diff.data, {'tool0': [100, 0]})
        diff.on_sent()
