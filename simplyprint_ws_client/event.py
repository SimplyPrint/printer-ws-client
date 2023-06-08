from abc import abstractmethod
from .timer import Intervals
from .printer_state import PrinterSettings

from enum import Enum
from typing import (
    Optional,
    Dict,
    List,
    Any,
    Union,
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
    WEBCAM_STATUS = "webcam_status"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"

class Event:
    name: str = ""
    data: Dict[str, Any] = {}
    
    # Generic event data
    def __init__(self, name: str, data: Dict[str, Any] = {}, *args, **kwargs):
        self.name = self.name or self.__class__.__name__
        self.data = data

        if self.name != name:
            raise ValueError(f"Event type {type} does not match event name {self.name}")
        
        self.on_event()

    @abstractmethod
    def on_event(self):
        """
        Secondary constructor for events, useful for when the event is received to avoid super calls
        """
        pass

    def __str__(self):
        return self.name

class ErrorEvent(Event):
    name = "error"

    def on_event(self):
        self.error: str = self.data.get("error", "")

class NewTokenEvent(Event):
    name = "new_token"

    def on_event(self):
        self.short_id: str = self.data.get("short_id", "")
        self.token: str = self.data.get("token", "")
        self.no_exist: bool = self.data.get("no_exist", False)

class ConnectEvent(Event):
    name = "connected"

    def on_event(self):
        self.in_set_up: bool = self.data.get("in_set_up", 0) == 1
        self.intervals: Intervals = Intervals(self.data.get("interval", {}))
        self.printer_settings: PrinterSettings = PrinterSettings(self.data.get("printer_settings", {}))
        self.short_id: Optional[str] = self.data.get("short_id")
        self.reconnect_token: Optional[str] = self.data.get("reconnect_token")
        self.name: Optional[str] = self.data.get("name")

class SetupCompleteEvent(Event):
    name = "complete_setup"

    def on_event(self):
        self.printer_id: str = self.data.get("printer_id", "")

class IntervalChangeEvent(Event):
    name = "interval_change"

    def on_event(self):
        self.intervals: Intervals = Intervals(self.data)

class PongEvent(Event):
    name = "pong"

class StreamReceivedEvent(Event):
    name = "stream_received"

class PrinterSettingsEvent(Event):
    name = "printer_settings"

    def on_event(self):
        self.printer_settings = PrinterSettings(self.data)

class DemandEvent(Event):
    name = "demand"
    demand: Union[str, List[str]] = ""

    def __init__(self, name: str, demand: str, data: Dict[str, Any] = {}):
        super().__init__(name, data)

        if self.demand not in self.demand:
            raise ValueError(f"Demand type {name} does not match demand {self.demand}")

        self.demand = demand

class PauseEvent(DemandEvent):
    demand = "pause"

class ResumeEvent(DemandEvent):
    demand = "resume"

class CancelEvent(DemandEvent):
    demand = "cancel"

class TerminalEvent(DemandEvent):
    demand = "terminal"

    def on_event(self):
        self.enabled: bool = self.data.get("enabled", False)

# TODO; Fix
class DisplayMessageEvent(DemandEvent):
    def __init__(self, message: str, short_branding: bool = False):
        self.message: str = message
        self.short_branding: bool = short_branding

class GcodeEvent(DemandEvent):
    demand = "gcode"

    def on_event(self):
        self.list: List[str] = self.data.get("list", [])

class WebcamTestEvent(DemandEvent):
    demand = "webcam_test"

class WebcamSnapshotEvent(DemandEvent):
    demand = "webcam_snapshot"
    
    def on_event(self):
        self.id: Optional[str] = self.data.get("id")
        self.timer: Optional[int] = self.data.get("timer")

class FileEvent(DemandEvent):
    demand = "file"

    def on_event(self):
        self.url: Optional[str] = self.data.get("url")
        self.path: Optional[str] = self.data.get("path")
        self.auto_start: bool = bool(self.data.get("auto_start", 0))

class StartPrintEvent(DemandEvent):
    demand = "start_print"

class ConnectPrinterEvent(DemandEvent):
    demand = "connect_printer"

class DisconnectPrinterEvent(DemandEvent):
    demand = "disconnect_printer"

class SystemRestartEvent(DemandEvent):
    demand = "system_restart"

class SystemShutdownEvent(DemandEvent):
    demand = "system_shutdown"

class ApiRestartEvent(DemandEvent):
    demand = "api_restart"

class ApiShutdownEvent(DemandEvent):
    demand = "api_shutdown"

class UpdateEvent(DemandEvent):
    demand = "update"

class PluginInstallEvent(DemandEvent):
    demand = "plugin_install"

class PluginUninstallEvent(DemandEvent):
    demand = "plugin_uninstall"

class WebcamSettingsEvent(DemandEvent):
    demand = "webcam_settings_updated"
    def on_event(self):
        self.webcam_settings = self.data.get("webcam_settings")

# deprecated
class StreamOnEvent(DemandEvent):
    demand = "stream_on"

    def on_event(self):
        self.interval: float = self.data.get("interval", 300.0) / 1000.0

# deprecated
class StreamOffEvent(DemandEvent):
    demand = "stream_off"

class SetPrinterProfileEvent(DemandEvent):
    demand = "set_printer_profile"

    def on_event(self):
        self.profile = self.data.get("printer_profile")

class GetGcodeScriptBackupsEvent(DemandEvent):
    demand = "get_gcode_script_backups"

    def on_event(self):
        self.force = self.data.get("force", False)

class HasGcodeChangesEvent(DemandEvent):
    demand = "has_gcode_changes"

    def on_event(self):
        self.scripts = self.data.get("scripts")

class PsuControlEvent(DemandEvent):
    demand = ["psu_on", "psu_off", "psu_keepalive"]

    def on_event(self):
        self.on: bool = self.demand != "psu_off"

class DisableWebsocketEvent(DemandEvent):
    demand = "disable_websocket"

    def on_event(self):
        self.websocket_ready: bool = self.data.get("websocket_ready", False)


# Construct hashmap of events (sub-hashmap for demands)
events: Dict[str, Union[Event, Dict[str, Event]]] = { event.name: event for event in Event.__subclasses__() if event.name != "demand" }
events["demand"] = { demand: event for event in DemandEvent.__subclasses__() for demand in (event.demand if isinstance(event.demand, list) else [event.demand]) }