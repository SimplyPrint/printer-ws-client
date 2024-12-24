import unittest

from simplyprint_ws_client.helpers import IntervalException, IntervalTypes, Intervals


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

        intervals.set(IntervalTypes.PING, 1000.0)

        self.assertEqual(intervals.intervals[IntervalTypes.PING.value], 1000.0)
        self.assertTrue(intervals.is_ready(IntervalTypes.PING))

        intervals.use(IntervalTypes.PING)

        self.assertFalse(intervals.is_ready(IntervalTypes.PING))
        self.assertEqual(intervals.time_until_ready(IntervalTypes.PING), 1.0)

        intervals.step_time(1000.0)

        self.assertTrue(intervals.is_ready(IntervalTypes.PING))
        self.assertEqual(intervals.time_until_ready(IntervalTypes.PING), 0.0)

        intervals.use(IntervalTypes.PING)

        self.assertFalse(intervals.is_ready(IntervalTypes.PING))
        self.assertEqual(intervals.time_until_ready(IntervalTypes.PING), 1.0)

        intervals.step_time(500.0)

        self.assertFalse(intervals.is_ready(IntervalTypes.PING))
        self.assertEqual(intervals.time_until_ready(IntervalTypes.PING), 0.5)

        self.assertRaises(IntervalException, intervals.use, IntervalTypes.PING)

        intervals.step_time(500.0)

        self.assertTrue(intervals.is_ready(IntervalTypes.PING))

        intervals.use(IntervalTypes.PING)

        self.assertFalse(intervals.is_ready(IntervalTypes.PING))
        self.assertEqual(intervals.time_until_ready(IntervalTypes.PING), 1.0)

        self.assertTrue(IntervalTypes.PING.value in intervals.intervals)
