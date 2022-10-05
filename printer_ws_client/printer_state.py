from enum import Enum
from typing import Optional, List

class Temperature:
    def __init__(self, actual: float = 0.0, target: Optional[float] = None):
        self.actual: float = actual
        self.target: Optional[float] = target

    def to_list(self) -> List[float]:
        out = [self.actual]

        if not self.target is None:
            out.append(self.target)

        return out

class PrinterStatus(Enum):
    OPERATIONAL = "operational"
    PRINTING = "printing"
    OFFLINE = "offline"
    PAUSED = "paused"
    PAUSING = "pausing"
    CANCELLING = "cancelling"
    ERROR = "error"

class Printer:
    def __init__(self): 
        self.connected: bool = False
        self.status: PrinterStatus = PrinterStatus.OFFLINE
        self.tool_temperatures: List[Temperature] = []
        self.bed_temperature: Optional[Temperature] = None
        self.layer: Optional[int] = None
