from typing import Any, Dict, List, Optional, Union
from .events import ServerEvent, ServerEventType, ServerEventTraits

class DemandEventTraits(ServerEventTraits):
    def __str__(cls):
        return cls.demand or cls.name
    
    def __repr__(cls) -> str:
        return f"<DemandEvent {cls.demand}>"

    def __eq__(cls, other: object) -> bool:
        if isinstance(other, str): return (cls.demand or cls.name) == other
        if isinstance(other, DemandEvent): return (cls.demand or cls.name) == (other.demand or other.name)
        return False

    def __hash__(cls) -> int:
        return hash(cls.demand or cls.name)

class DemandEventType(ServerEventType, DemandEventTraits):
    def __repr__(cls) -> str:
        return f"<DemandEvent {cls.demand}>"

class DemandEvent(ServerEvent, DemandEventTraits, metaclass=DemandEventType):
    name = "demand"
    demand: Union[str, List[str]] = ""

    def __init__(self, name: str, demand: str, data: Dict[str, Any] = {}):
        super().__init__(name, data)

        if demand not in self.demand:
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
        self.auto_start: bool = bool(self.data.get("auto_start", 0))
        self.url: Optional[str] = self.data.get("url")
        self.cdn_url: Optional[str] = self.data.get("cdn_url")
        self.file_name: Optional[str] = self.data.get("file_name")
        self.file_id: str = self.data.get("file_id")
        self.file_size: Optional[int] = self.data.get("file_size")
        self.start_options: Dict[str, bool] = self.data.get("start_options", None)
        self.mms_map: Dict[str, Any] = self.data.get("mms_map", None)

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