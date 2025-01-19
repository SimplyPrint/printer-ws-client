__all__ = [
    'PrinterCpuFlag',
    'PrinterStatus',
    'FileProgressStateEnum',
    'FilamentSensorEnum',
    'Intervals',
    'DisplaySettings',
    'PrinterSettings',
]

import asyncio
import time
from enum import IntEnum, StrEnum
from typing import Optional, Self, Dict, Any, Literal

from pydantic import BaseModel


class PrinterCpuFlag(IntEnum):
    NONE = 0
    THROTTLED = 1


class PrinterStatus(StrEnum):
    OPERATIONAL = "operational"
    PRINTING = "printing"
    OFFLINE = "offline"
    PAUSED = "paused"
    PAUSING = "pausing"
    CANCELLING = "cancelling"
    RESUMING = "resuming"
    ERROR = "error"
    NOT_READY = "not_ready"


class FileProgressStateEnum(StrEnum):
    DOWNLOADING = "downloading"
    ERROR = "error"
    PENDING = "pending"
    STARTED = "started"
    READY = "ready"


class FilamentSensorEnum(StrEnum):
    LOADED = "loaded"
    RUNOUT = "runout"


IntervalT = Literal[
    "ai", "job", "temps", "temps_target", "cpu", "reconnect", "ready_message", "ping", "webcam"]


class Intervals(BaseModel):
    ai: int = 30000
    job: int = 5000
    temps: int = 5000
    temps_target: int = 2500
    cpu: int = 30000
    reconnect: int = 1000
    ready_message: int = 60000
    ping: int = 20000
    webcam: int = 1000

    _usages: Dict[str, int]

    def model_post_init(self, __context: Any) -> None:
        self._usages = {key: 0 for key in self.model_fields.keys()}

    @staticmethod
    def now() -> int:
        return int(time.monotonic_ns() / 1_000_000)

    def time_until_ready(self, t: IntervalT) -> int:
        return self.now() - self._usages[t] - getattr(self, t)

    def is_ready(self, t: IntervalT):
        return self.now() - self._usages[t] >= getattr(self, t)

    def dispatch_mode(self, t: IntervalT):
        from ..ws_protocol.messages import DispatchMode

        if not self.use(t):
            return DispatchMode.RATELIMIT

        return DispatchMode.DISPATCH

    def use(self, t: IntervalT) -> bool:
        if not self.is_ready(t):
            return False

        self._usages[t] = self.now()

        return True

    async def wait_for(self, t: IntervalT):
        while not self.is_ready(t):
            s = self.time_until_ready(t) / 1000

            if s <= 0.0:
                break

            await asyncio.sleep(s)

    def set(self, t: IntervalT, value: int):
        setattr(self, t, value)

    def update(self, other: Self):
        for key in other.model_fields.keys():
            setattr(self, key, getattr(other, key))


class DisplaySettings(BaseModel):
    enabled: bool = True
    branding: bool = True
    while_printing_type: int = 0
    show_status: bool = True


class PrinterSettings(BaseModel):
    has_psu: bool = False
    has_filament_settings: bool = False
    display: Optional[DisplaySettings] = None
