import unittest

from pydantic import Field

from simplyprint_ws_client import AmbientTemperatureState, StateModel, TemperatureState


class TestState(StateModel):
    ambient: AmbientTemperatureState = Field(defaut_factory=AmbientTemperatureState)


class TestAmbientTemperature(unittest.TestCase):
    def test_simple(self):
        tools = [TemperatureState(actual=27.21875, target=0.0)]

        state = TestState(ambient=AmbientTemperatureState())

        for i in range(100):
            state.ambient.invoke_check(tools)

        self.assertEqual(state.ambient.ambient, 27)
