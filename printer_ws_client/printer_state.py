from enum import Enum
from typing import Optional, List, Dict, Any

class Temperature:
    def __init__(self, actual: float = 0.0, target: Optional[float] = None):
        self.actual: float = actual
        self.target: Optional[float] = target

    def __eq__(self, other) -> bool:
        if not isinstance(other, Temperature):
            return False

        return self.actual == other.actual and self.target == other.target

    def to_list(self) -> List[int]:
        out = [round(self.actual)]

        if not self.target is None:
            out.append(round(self.target))

        return out

class PrinterStatus(Enum):
    OPERATIONAL = "operational"
    PRINTING = "printing"
    OFFLINE = "offline"
    PAUSED = "paused"
    PAUSING = "pausing"
    CANCELLING = "cancelling"
    ERROR = "error"

class Display:
    def __init__(self, data: Dict[str, Any]):
        self.enabled: bool = bool(data.get("enabled", 0))
        self.branding: bool = bool(data.get("branding", 0))
        self.while_printing_type: int = data.get("while_printing_type", 0)
        self.show_status: bool = bool(data.get("show_status", 0))

class PrinterSettings:
    def __init__(self, data: Dict[str, Any] = {}):
        self.has_psu: bool = bool(data.get("has_psu", 0))
        self.has_filament_sensor: bool = bool(data.get("has_filament_sensor", 0))
        self.display: Display = Display(data.get("display", {}))

class Printer:
    def __init__(self): 
        self.connected: bool = False
        self.is_set_up: bool = False
        self.status: PrinterStatus = PrinterStatus.OFFLINE
        self.tool_temperatures: List[Temperature] = []
        self.server_tool_temperatures: List[Temperature] = []
        self.bed_temperature: Optional[Temperature] = None
        self.server_bed_temperature: Optional[Temperature] = None
        self.layer: Optional[int] = None
        self.settings: PrinterSettings = PrinterSettings()
        self.name: Optional[str] = None
