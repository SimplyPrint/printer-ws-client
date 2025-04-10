__all__ = [
    'PrinterCpuFlag',
    'PrinterStatus',
    'FileProgressStateEnum',
    'FilamentSensorEnum',
    'Intervals',
    'DisplaySettings',
    'PrinterSettings',
    'MultiMaterialSolution',
]

import asyncio
import time
from enum import IntEnum, StrEnum, Enum
from typing import Optional, Dict, Any, Literal

from pydantic import BaseModel, PrivateAttr

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


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
    DOWNLOADING = "downloading"
    ERROR = "error"
    NOT_READY = "not_ready"

    @staticmethod
    def is_printing(*status: Optional['PrinterStatus']) -> bool:
        return len(set(status).intersection({
            PrinterStatus.PRINTING,
            PrinterStatus.PAUSED,
            PrinterStatus.PAUSING,
            PrinterStatus.RESUMING,
            PrinterStatus.CANCELLING,
        })) > 0


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

    _usages: Dict[str, Optional[int]] = PrivateAttr(...)

    def model_post_init(self, __context: Any) -> None:
        self._usages = {key: None for key in self.model_fields.keys()}

    @staticmethod
    def now() -> int:
        return int(time.monotonic_ns() / 1_000_000)

    def time_until_ready(self, t: IntervalT) -> int:
        if self._usages[t] is None:
            return 0

        return getattr(self, t) - (self.now() - self._usages[t])

    def is_ready(self, t: IntervalT):
        if self._usages[t] is None:
            return True

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
        while True:
            time_remaining = self.time_until_ready(t)

            if time_remaining <= 0:
                break

            await asyncio.sleep(time_remaining / 1000.0)

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


class MultiMaterialSolution(Enum):
    BAMBU_AMS = "bambu_ams"
    BAMBU_AMS_2_PRO = "bambu_ams_2_pro"
    BAMBU_AMS_HT = "bambu_ams_ht"
    BAMBU_AMS_LITE = "bambu_ams_lite"
    PRUSA_MMU3 = "prusa_mmu3"
    MOSAICPALETTE2S = "mosaic_palette2s"
    MOSAICPALETTE2 = "mosaic_palette2"
    BOXTURTLE = "boxturtle"
    CREALITY_CFS = "creality_cfs"
    CUSTOM = "custom"
