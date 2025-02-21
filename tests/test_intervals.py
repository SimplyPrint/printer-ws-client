import unittest

from simplyprint_ws_client import Intervals


class TimeControlledIntervals(Intervals):
    ms_time: float = 30000.0

    @classmethod
    def set_time(cls, ms: float) -> None:
        cls.ms_time = ms

    @classmethod
    def step_time(cls, ms: float) -> None:
        cls.ms_time += ms

    @classmethod
    def now(cls) -> float:
        return cls.ms_time


class TestConfigManager(unittest.TestCase):
    def test_intervals(self):
        intervals = TimeControlledIntervals()
        intervals.set_time(30000.0)

        self.assertEqual(intervals.now(), 30000.0)

        intervals.set("ping", 1000)

        self.assertEqual(intervals.ping, 1000.0)
        self.assertTrue(intervals.is_ready("ping"))

        intervals.use("ping")

        self.assertFalse(intervals.is_ready("ping"))
        self.assertEqual(intervals.time_until_ready("ping"), 1000)

        intervals.step_time(1000.0)

        self.assertTrue(intervals.is_ready("ping"))
        self.assertEqual(intervals.time_until_ready("ping"), 0)

        intervals.use("ping")

        self.assertFalse(intervals.is_ready("ping"))
        self.assertEqual(intervals.time_until_ready("ping"), 1000)

        intervals.step_time(500.0)

        self.assertFalse(intervals.is_ready("ping"))
        self.assertEqual(intervals.time_until_ready("ping"), 500)
        self.assertFalse(intervals.use("ping"))

        intervals.step_time(500.0)

        self.assertTrue(intervals.is_ready("ping"))

        intervals.use("ping")

        self.assertFalse(intervals.is_ready("ping"))
        self.assertEqual(intervals.time_until_ready("ping"), 1000)
