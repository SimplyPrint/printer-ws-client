import unittest

from traitlets import Instance

from simplyprint_ws_client.client.state import AmbientTemperatureState, Temperature, State


class TestState(State):
    ambient: AmbientTemperatureState = Instance(AmbientTemperatureState)


class TestAmbientTemperature(unittest.TestCase):
    def test_simple(self):
        tools = [Temperature(actual=27.21875, target=0.0)]

        state = TestState(ambient=AmbientTemperatureState())

        for i in range(100):
            state.ambient.invoke_check(tools)

        self.assertEqual(state.ambient.ambient, 28)
