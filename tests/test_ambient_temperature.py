import time
import unittest

from pydantic import BaseModel

from simplyprint_ws_client import PrinterStatus, PrinterState


class CustomTime(BaseModel):
    _time: float = 0
    _fail: bool = False

    def fail(self):
        self._fail = True

    def set(self, t: float):
        self._time = t

    def time(self) -> float:
        if self._fail:
            return -1

        return self._time


class TestState(PrinterState):
    config: None = None
    time: CustomTime

    # Progress ambient state n-steps
    def do(self, n=2):
        for _ in range(n):
            self.time.set(self.time.time() + self.ambient_temperature._update_interval)
            self.ambient_temperature.tick(self)


class TestAmbientTemperature(unittest.TestCase):
    def setUp(self):
        custom_time = CustomTime()
        time.time = lambda: custom_time.time()
        self.state = TestState(time=custom_time)
        self.state.set_nozzle_count(1)

    def test_simple(self):
        tool0 = self.state.tool_temperatures[0]

        tool0.actual = 27.21875
        tool0.target = 0.0

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 27)

    def test_with_printing_state(self):
        tool0 = self.state.tool_temperatures[0]

        tool0.actual = 27.21875
        tool0.target = 0.0

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 27)

        tool0.target = 200.0
        tool0.actual = 150.0

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 27)

        self.state.status = PrinterStatus.PRINTING
        tool0.actual = 200.0

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 27)

        self.state.status = PrinterStatus.OPERATIONAL
        tool0.target = 0

        # Cool down of 5 degrees per check - no change
        for _ in range(35):
            self.state.do(1)
            tool0.actual -= 5
            self.assertEqual(self.state.ambient_temperature.ambient, 27)

        # Now temperature is 25 degrees and we do 2 checks
        self.state.do()
        # New ambient temperature is 25
        self.assertEqual(self.state.ambient_temperature.ambient, 25)

    def test_fail_case(self):
        tool0 = self.state.tool_temperatures[0]

        tool0.actual = 27.21875
        tool0.target = 0.0

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 27)

        tool0.actual = 30

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 30)

        tool0.actual = 25

        self.state.time.fail()

        self.state.do()

        self.assertEqual(self.state.ambient_temperature.ambient, 30)
