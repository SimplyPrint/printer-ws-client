from typing import Any, Dict, List, Optional, Union

from .server_events import ServerEvent


class DemandEvent(ServerEvent):
    event_type = "demand"
    demand: Union[str, List[str]] = ""

    def __init__(self, name: str, demand: str, data: Dict[str, Any] = {}):
        super().__init__(name, data)

        if demand not in self.demand:
            raise ValueError(f"Demand type {name} does not match demand {self.demand}")

        self.demand = demand

    @classmethod
    def get_name(cls) -> Optional[str]:
        if cls is DemandEvent:
            return DemandEvent.__name__

        return cls.demand or cls.event_type


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
    demand = "test_webcam"


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
        self.start_options: Dict[str, bool] = self.data.get("start_options", {})
        self.zip_printable: Optional[str] = self.data.get("zip_printable")

        # Convert mapping to list of integers where -1 is None
        mms_map = self.data.get("mms_map", None)
        self.mms_map: Optional[List[int]] = list(
            map(lambda n: -1 if n is None else n, mms_map)) if mms_map is not None else None


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

    def on_event(self):
        self.plugins: List[Dict] = self.data.get("plugins")


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
    demand = "psu_keepalive"

    def on_event(self):
        self.on: bool = True


class PsuOnControlEvent(PsuControlEvent):
    demand = "psu_on"

    def on_event(self):
        self.on: bool = True


class PsuOffControlEvent(PsuControlEvent):
    demand = "psu_off"

    def on_event(self):
        self.on: bool = False


class DisableWebsocketEvent(DemandEvent):
    demand = "disable_websocket"

    def on_event(self):
        self.websocket_ready: bool = self.data.get("websocket_ready", False)


class SendLogsEvent(DemandEvent):
    demand = "send_logs"

    def on_event(self):
        self.token: str = self.data.get("token", "")
        self.logs: List[str] = self.data.get("logs", "")
        self.max_body = self.data.get("max_body", 100000000)

        self.send_main: bool = "main" in self.logs
        self.send_plugin: bool = "plugin_log" in self.logs
        self.send_serial: bool = "serial_log" in self.logs
