import asyncio
from collections import namedtuple
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Union

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

IntervalType = namedtuple('IntervalType', ['name', 'default_timing'])

class IntervalException(ValueError):
    pass

class IntervalTypes(Enum):
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
        return [t.value for t in cls]

class Intervals:
    intervals: Dict[IntervalType, float]
    last_updates: Dict[IntervalType, float]

    def __init__(self, data: Dict[Union[str, IntervalType], float] = {}):
        self.intervals = {}
        self.last_updates = {}
        
        for t, interval in data.items():
            if isinstance(t, str): t = self._get_type_from_str(t)
            self.intervals[t.name] = (interval or t.default_timing) / 1000.0
            self.last_updates[t.name] = datetime.now() - timedelta(seconds=self.intervals[t.name])

        for t in IntervalTypes.values():
            if t not in self.intervals:
                self.intervals[t.name] = t.default_timing / 1000.0
                self.last_updates[t.name] = datetime.now() - timedelta(seconds=self.intervals[t.name])

    def update(self, other: Self):
        for t, interval in other.intervals.items():
            self.intervals[t] = interval

    def set(self, t: IntervalType, interval: float):
        self.intervals[t.name] = (interval or t.default_timing) / 1000.0
        
        if not t.name in self.last_updates:
            self.last_updates[t.name] = datetime.now() - timedelta(seconds=self.intervals[t.name])
            
    def update_raw(self, data: Dict[Union[str, IntervalType], float]):
        for t, interval in data.items():
            if isinstance(t, str): t = self._get_type_from_str(t)
            self.intervals[t.name] = interval

    def time_until_ready(self, t: IntervalType) -> float:
        if t.name not in self.intervals:
            return 0.0

        return (datetime.now() - self.last_updates[t.name]).total_seconds()
        
    def is_ready(self, t: IntervalType) -> bool:
        if t.name not in self.intervals:
            return True 
        
        return self.time_until_ready(t) <= 0.0
        
    async def wait_until_ready(self, t: IntervalType):
        if not t.name in self.intervals:
            return

        ready_in_seconds = self.time_until_ready(t)

        if ready_in_seconds <= 0.0:
            return
        
        await asyncio.sleep(ready_in_seconds)

    def use(self, t: IntervalType):
        if not self.is_ready(t):
            raise IntervalException(f"Interval {t.name} is not ready until {self.time_until_ready(t)} (now: {datetime.now()})")

        self.last_updates[t.name] = datetime.now()

    def _get_type_from_str(self, t: str) -> IntervalType:
        return IntervalTypes[t.upper()].value