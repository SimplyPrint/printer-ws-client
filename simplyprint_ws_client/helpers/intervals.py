import asyncio
import time
from enum import Enum
from typing import Dict, List, Union, NamedTuple, Optional

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


class IntervalException(ValueError):
    pass


# An interval can be referred to by its name, its IntervalType or its IntervalTypes
IntervalTypeRef = Union[str, 'IntervalType', 'IntervalTypes']


class IntervalType(NamedTuple):
    """And interval has a name and a timing, here we can define the default timing"""
    name: str
    default_timing: float

    def __hash__(self) -> int:
        return hash(self.name)


class IntervalTypes(Enum):
    """A list of all the intervals that can be used"""

    AI = IntervalType("ai", 30000)
    JOB = IntervalType("job", 5000)
    TEMPS = IntervalType("temps", 5000)
    TEMPS_TARGET = IntervalType("temps_target", 2500)
    CPU = IntervalType("cpu", 30000)
    RECONNECT = IntervalType("reconnect", 1000)
    READY_MESSAGE = IntervalType("ready_message", 60000)
    PING = IntervalType("ping", 20000)
    WEBCAM = IntervalType("webcam", 1000)

    @classmethod
    def values(cls) -> List[IntervalType]:
        """Returns a list of all default valid intervals"""
        return [t.value for t in cls]

    @classmethod
    def from_str(cls, name: str) -> IntervalType:
        """Get an interval from its name"""
        return cls[name.upper()].value

    @classmethod
    def from_any(cls, t: IntervalTypeRef) -> IntervalType:
        """Convert an intervaltyperef to an intervaltype"""
        if isinstance(t, IntervalType):
            return t

        if isinstance(t, IntervalTypes):
            return t.value

        if isinstance(t, str):
            return cls.from_str(t)

        raise ValueError(f"Could not convert {t} to IntervalType")

    def __hash__(self) -> int:
        return hash(self.value)


class Intervals:
    intervals: Dict[IntervalType, float]
    last_updates: Dict[IntervalType, float]

    @classmethod
    def now(cls) -> float:
        """ Returns the current time in milliseconds """
        return time.time() * 1000.0

    @classmethod
    def choose_interval(cls, t: IntervalType, interval_ms: Optional[float]) -> float:
        """ Chooses the interval to use based on the given interval_ms """
        if interval_ms is None:
            return t.default_timing

        if interval_ms > 0.0:
            return interval_ms

        return t.default_timing

    def __init__(self, data=None):
        """Construct the class from external arguments and fill in the rest with the defaults"""
        self.intervals = {}
        self.last_updates = {}

        if data:
            for t, interval in data.items():
                t = IntervalTypes.from_any(t)
                self.intervals[t] = self.choose_interval(t, interval)
                self.last_updates[t] = self.now() - self.intervals[t]

        for t in IntervalTypes.values():
            if t in self.intervals:
                continue

            self.intervals[t] = self.choose_interval(t, None)
            self.last_updates[t] = self.now() - self.intervals[t]

    def update(self, other: Self):
        """Update the intervals with the intervals from another Intervals object"""
        for t, interval in other.intervals.items():
            t = IntervalTypes.from_any(t)
            self.intervals[t] = interval

    def set(self, t: IntervalTypeRef, interval: float):
        """Set the interval for a given interval type"""
        t = IntervalTypes.from_any(t)
        self.intervals[t] = self.choose_interval(t, interval)

        if t not in self.last_updates:
            self.last_updates[t] = self.now() - self.intervals[t]

    def update_raw(self, data: Dict[IntervalTypeRef, float]):
        """Update the intervals with the intervals from a dict"""
        for t, interval in data.items():
            t = IntervalTypes.from_any(t)
            self.intervals[t] = interval

    def time_until_ready(self, t: IntervalTypeRef) -> float:
        """Get the time until an interval is ready"""
        t = IntervalTypes.from_any(t)

        if t not in self.intervals:
            return t.default_timing

        ms_until_ready = self.intervals[t] - (self.now() - self.last_updates[t])

        # Convert to seconds
        return ms_until_ready / 1000.0

    def is_ready(self, t: IntervalTypeRef) -> bool:
        t = IntervalTypes.from_any(t)

        if t not in self.intervals:
            return True

        return self.time_until_ready(t) <= 0.0

    async def wait_until_ready(self, t: IntervalTypeRef):
        """Wait until an interval is ready"""
        t = IntervalTypes.from_any(t)

        if t not in self.intervals:
            return

        ready_in_seconds = self.time_until_ready(t)

        if ready_in_seconds <= 0.0:
            return

        await asyncio.sleep(ready_in_seconds)

        if not self.is_ready(t):
            raise IntervalException(
                f"Interval did not become ready in time: {ready_in_seconds} seconds remaining {self.time_until_ready(t)}")

    def use(self, t: IntervalTypeRef):
        """Update the last update time for an interval"""

        t = IntervalTypes.from_any(t)

        if not self.is_ready(t):
            raise IntervalException(
                f"Interval {t} is ready in {self.time_until_ready(t)} seconds")

        self.last_updates[t] = self.now()
