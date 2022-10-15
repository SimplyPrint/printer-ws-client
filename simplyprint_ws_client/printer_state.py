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

    def heating(self) -> bool:
        if self.target is None:
            return False

        return round(self.actual) != round(self.target)

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

class PrinterFirmware:
    name: Optional[str] = None
    version: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None

    def dict(self) -> Dict[str, Any]:
        return {
            "firmware": self.name,
            "firmware_version": self.version,
            "firmware_date": self.date,
            "firmware_link": self.link
        }

class PrinterCpuFlag(Enum):
    NONE = 0
    THROTTLED = 1

class Printer:
    connected: bool = False
    is_set_up: bool = False
    status: PrinterStatus = PrinterStatus.OFFLINE

    ambient_temperature: Optional[float] = None 

    tool_temperatures: List[Temperature] = []
    bed_temperature: Optional[Temperature] = None

    server_tool_temperatures: List[Temperature] = []
    server_bed_temperature: Optional[Temperature] = None

    name: Optional[str] = None

    settings: PrinterSettings = PrinterSettings()
    firmware: PrinterFirmware = PrinterFirmware()
    current_display_message: Optional[str] = None

    def is_heating(self) -> bool:
        for tool in self.tool_temperatures:
            if tool.heating():
                return True

        if self.bed_temperature is not None and self.bed_temperature.heating():
            return True

        return False
