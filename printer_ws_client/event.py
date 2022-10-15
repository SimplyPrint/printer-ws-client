from .timer import Intervals
from .printer_state import PrinterSettings

from enum import Enum
from typing import (
    Optional,
    Dict,
    List,
    Any,
)

class PrinterEvent(Enum):
    PING = "ping"
    LATENCY = "latency"
    TOOL = "tool"
    STATUS = "state_change"
    AMBIENT = "ambient"
    TEMPERATURES = "temps"
    SHUTDOWN = "shutdown"
    CONNECTION = "connection"
    CAMERA_SETTINGS = "camera_settings"
    GCODE_TERMINAL = "gcode_terminal"
    JOB_UPDATE = "job_update"
    JOB_INFO = "job_info"
    PLUGIN_INSTALLED = "plugin_installed"
    FILE_PROGRESS = "file_progress"
    PSU_CHANGE = "psu_change"
    CPU = "cpu"
    STREAM = "stream"
    MESH_DATA = "mesh_data"
    MACHINE_DATA = "machine_data"
    PRINT_STARTED = "print_started"
    PRINT_DONE = "print_done"
    PRINT_PAUSING = "print_pausing"
    PRINT_PAUSED = "print_paused"
    PRINT_CANCELLED = "print_cancelled"
    PRINT_FALIURE = "print_failure"
    PRINTER_ERROR = "printer_error"
    INPUT_REQUIRED = "input_required"
    UPDATE_STARTED = "update_started"
    FIRMWARE = "firmware"
    AI_RESPONSE = "ai_resp"
    WEBCAM_STATUS = "webcam_status"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"

class Event:
    def __init__(self):        
        pass

class ErrorEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.error: str = data.get("error", "")

class NewTokenEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.short_id: str = data.get("short_id", "")
        self.token: str = data.get("token", "")
        self.no_exist: bool = data.get("no_exist", False)

class ConnectEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.in_set_up: bool = data.get("in_set_up", 0) == 1
        self.intervals: Intervals = Intervals(data.get("interval", {}))
        self.printer_settings: PrinterSettings = PrinterSettings(data.get("printer_settings", {}))
        self.short_id: Optional[str] = data.get("short_id")
        self.reconnect_token: Optional[str] = data.get("reconnect_token")
        self.name: Optional[str] = data.get("name")

class SetupCompleteEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.printer_id: str = data.get("printer_id", "")

class IntervalChangeEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.intervals: Intervals = Intervals(data)

class PongEvent(Event):
    def __init__(self):
        pass

class StreamReceivedEvent(Event):
    def __init__(self):
        pass

class PrinterSettingsEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.printer_settings: PrinterSettings = PrinterSettings(data)

class PauseEvent(Event):
    def __init__(self):
        pass

class ResumeEvent(Event):
    def __init__(self):
        pass

class CancelEvent(Event):
    def __init__(self):
        pass

class TerminalEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.enabled: bool = data.get("enabled", False)

class DisplayMessageEvent(Event):
    def __init__(self, message: str, short_branding: bool = False):
        self.message: str = message
        self.short_branding: bool = short_branding

class GcodeEvent(Event):
    def __init__(self, data: Dict[str, Any] = {}):
        self.list: List[str] = data.get("list", [])

class WebcamTestEvent(Event):
    def __init__(self):
        pass

class WebcamSnapshotEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.id: Optional[str] = data.get("id")
        self.timer: Optional[int] = data.get("timer")

class FileEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.url: Optional[str] = data.get("url")
        self.path: Optional[str] = data.get("path")
        self.auto_start: bool = bool(data.get("auto_start", 0))

class StartPrintEvent(Event):
    def __init__(self):
        pass

class ConnectPrinterEvent(Event):
    def __init__(self):
        pass

class DisconnectPrinterEvent(Event):
    def __init__(self):
        pass

class SystemRestartEvent(Event):
    def __init__(self):
        pass

class SystemShutdownEvent(Event):
    def __init__(self):
        pass

class ApiRestartEvent(Event):
    def __init__(self):
        pass

class ApiShutdownEvent(Event):
    def __init__(self):
        pass

class UpdateEvent(Event):
    def __init__(self):
        pass

class PluginInstallEvent(Event):
    def __init__(self):
        pass

class PluginUninstallEvent(Event):
    def __init__(self):
        pass

class WebcamSettingsEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.webcam_settings = data.get("webcam_settings")

# deprecated
class StreamOnEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.interval: float = data.get("interval", 300.0) / 1000.0

# deprecated
class StreamOffEvent(Event):
    def __init__(self):
        pass

class SetPrinterProfileEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.profile = data.get("printer_profile")

class GetGcodeScriptBackupsEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.force = data.get("force", False)

class HasGcodeChangesEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.scripts = data.get("scripts")

class PsuControlEvent(Event):
    def __init__(self, on: bool):
        self.on: bool = on

class DisableWebsocketEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.websocket_ready: bool = data.get("websocket_ready", False)
