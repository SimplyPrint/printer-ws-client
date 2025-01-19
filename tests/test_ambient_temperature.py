import unittest

from traitlets import Instance

from simplyprint_ws_client.core.state import AmbientTemperatureState, StateModel, TemperatureState


class TestState(StateModel):
    ambient: AmbientTemperatureState = Instance(AmbientTemperatureState)


class TestAmbientTemperature(unittest.TestCase):
    def test_simple(self):
        tools = [TemperatureState(actual=27.21875, target=0.0)]

        state = TestState(ambient=AmbientTemperatureState())

        for i in range(100):
            state.ambient.invoke_check(tools)

        self.assertEqual(state.ambient.ambient, 27)
