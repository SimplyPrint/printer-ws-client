from typing import ClassVar

from simplyprint_ws_client import Intervals


class TimeControlledIntervals(Intervals):
    ms_time: ClassVar[float] = 30000.0

    @classmethod
    def set_time(cls, ms: float) -> None:
        cls.ms_time = ms

    @classmethod
    def step_time(cls, ms: float) -> None:
        cls.ms_time += ms

    @classmethod
    def now(cls) -> float:
        return cls.ms_time


def test_intervals():
    intervals = TimeControlledIntervals()
    intervals.set_time(30000.0)

    assert intervals.now() == 30000.0

    intervals.set("ping", 1000)

    assert intervals.ping == 1000.0
    assert intervals.is_ready("ping")

    intervals.use("ping")

    assert not intervals.is_ready("ping")
    assert intervals.time_until_ready("ping") == 1000

    intervals.step_time(1000.0)

    assert intervals.is_ready("ping")
    assert intervals.time_until_ready("ping") == 0

    intervals.use("ping")

    assert not intervals.is_ready("ping")
    assert intervals.time_until_ready("ping") == 1000

    intervals.step_time(500.0)

    assert not intervals.is_ready("ping")
    assert intervals.time_until_ready("ping") == 500
    assert not intervals.use("ping")

    intervals.step_time(500.0)

    assert intervals.is_ready("ping")

    intervals.use("ping")

    assert not intervals.is_ready("ping")
    assert intervals.time_until_ready("ping") == 1000
