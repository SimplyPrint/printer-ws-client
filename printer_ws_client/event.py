from .timer import Intervals
from .printer_state import PrinterSettings

from typing import (
    Optional,
    Callable, 
    Dict,
    List,
    Any,
)

class EventCallbacks:
    def __init__(self):
        self.on_event: Callable[[Event], None] = lambda _: None

        self.on_error: Callable[[ErrorEvent], None] = lambda _: None
        self.on_new_token: Callable[[NewTokenEvent], None] = lambda _: None
        self.on_connect: Callable[[ConnectEvent], None] = lambda _: None
        self.on_setup_complete: Callable[[SetupCompleteEvent], None] = lambda _: None
        self.on_interval_change: Callable[[IntervalChangeEvent], None] = lambda _: None
        self.on_pong: Callable[[PongEvent], None] = lambda _: None
        self.on_stream_received: Callable[[StreamReceivedEvent], None] = lambda _: None
        self.on_printer_settings: Callable[[PrinterSettingsEvent], None] = lambda _: None
        
        self.on_pause: Callable[[PauseEvent], None] = lambda _: None
        self.on_resume: Callable[[ResumeEvent], None] = lambda _: None
        self.on_cancel: Callable[[CancelEvent], None] = lambda _: None
        self.on_terminal: Callable[[TerminalEvent], None] = lambda _: None
        self.on_gcode: Callable[[GcodeEvent], None] = lambda _: None
        self.on_webcam_test: Callable[[WebcamTestEvent], None] = lambda _: None  
        self.on_webcam_snapshot: Callable[[WebcamSnapshotEvent], None] = lambda _: None
        self.on_file: Callable[[FileEvent], None] = lambda _: None
        self.on_start_print: Callable[[StartPrintEvent], None] = lambda _: None
        self.on_connect_printer: Callable[[ConnectPrinterEvent], None] = lambda _: None
        self.on_disconnect_printer: Callable[[DisconnectPrinterEvent], None] = lambda _: None
        self.on_system_restart: Callable[[SystemRestartEvent], None] = lambda _: None
        self.on_system_shutdown: Callable[[SystemShutdownEvent], None] = lambda _: None
        self.on_api_restart: Callable[[ApiRestartEvent], None] = lambda _: None
        self.on_api_shutdown: Callable[[ApiShutdownEvent], None] = lambda _: None
        self.on_update: Callable[[UpdateEvent], None] = lambda _: None
        self.on_plugin_install: Callable[[PluginInstallEvent], None] = lambda _: None
        self.on_plugin_uninstall: Callable[[PluginUninstallEvent], None] = lambda _: None
        self.on_webcam_settings: Callable[[WebcamSettingsEvent], None] = lambda _: None
        self.on_stream_on: Callable[[StreamOnEvent], None] = lambda _: None
        self.on_stream_off: Callable[[StreamOffEvent], None] = lambda _: None
        self.on_set_printer_profile: Callable[[SetPrinterProfileEvent], None] = lambda _: None
        self.on_get_gcode_script_backups: Callable[[GetGcodeScriptBackupsEvent], None] = lambda _: None
        self.on_has_gcode_changes: Callable[[HasGcodeChangesEvent], None] = lambda _: None
        self.on_psu_control: Callable[[PsuControlEvent], None] = lambda _: None
        self.on_disable_websocket: Callable[[DisableWebsocketEvent], None] = lambda _: None

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

class GcodeEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.list: List[str] = data.get("list", [])

class WebcamTestEvent(Event):
    def __init__(self):
        pass

class WebcamSnapshotEvent(Event):
    def __init__(self):
        pass

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
        self.interval: float = data.get("interval", 300.0) / 300.0

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
