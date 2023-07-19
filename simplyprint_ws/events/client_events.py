from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, Generator, Tuple, Optional, Set, Any
from toml import TomlDecoder

from traitlets import HasTraits

from ..const import VERSION

from enum import Enum

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
    PSU = "power_controller"
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
    WEBCAM = "webcam"
    WEBCAM_STATUS = "webcam_status"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"

class ClientEvent:
    event_type: str
    
    state: Any
    forClient: Optional[int]
    data: Optional[Dict[str, Any]]

    def __init__(self, state = None, forClient: Optional[int] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """
        state (PrinterState): The state of the printer at the time of the event.
        forClient (int): Id of client event belongs to
        data (Optional[Dict[str, Any]], optional): Custom data to send with the event. Defaults to None.
        """
        self.state = state
        self.forClient = forClient
        self.data = data

    @abstractmethod
    def generate_data(self) -> Optional[Generator[Tuple, None, None]]:
        pass

    def generate(self) -> Generator[Tuple, None, None]:
        yield "type", self.event_type

        if not self.forClient is None and self.forClient != 0:
            yield "for", self.forClient

        if self.data is not None:
            yield "data", self.data
        elif (data_generator := self.generate_data()) is not None:
            yield "data", dict(data_generator)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.generate())

class GcodeScriptsEvent(ClientEvent):
    event_type = "gcode_scripts"

class MachineDataEvent(ClientEvent):
    event_type = PrinterEvent.MACHINE_DATA.value
    
    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.machine_data.trait_values().items():
            if self.state.has_changed(self.state.machine_data, key):
                yield key, value
    
class WebcamStatusEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM_STATUS.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "connected", self.state.webcam_info.connected

class WebcamEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.webcam_settings.trait_values().items():
            if self.state.has_changed(self.state.webcam_settings, key):
                yield key, value

class InstalledPluginsEvent(ClientEvent):
    event_type = "installed_plugins"

class SoftwareUpdatesEvent(ClientEvent):
    event_type = "software_updates"

class FirmwareEvent(ClientEvent):
    event_type = "firmware"

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.firmware.trait_values().items():
            if self.state.has_changed(self.state.firmware, key):
                yield f"firmware_{key}", value

class FirmwareWarningEvent(ClientEvent):
    event_type = "firmware_warning"

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.firmware.trait_values().items():
            yield key, value

class ToolEvent(ClientEvent):
    event_type = PrinterEvent.TOOL.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "active_tool", 0

class TemperatureEvent(ClientEvent):
    event_type = PrinterEvent.TEMPERATURES.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        if self.state.has_changed(self.state.bed_temperature):
            yield "bed", self.state.bed_temperature.to_list()

        for i, tool in enumerate(self.state.tool_temperatures):
            if self.state.has_changed(TomlDecoder):
                yield f"tool{i}", tool.to_list()

class AmbientTemperatureEvent(ClientEvent):
    event_type = "ambient"

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "new", round(self.state.ambient_temperature.ambient)

class ConnectionEvent(ClientEvent):
    event_type = "connection"

class StateChangeEvent(ClientEvent):
    event_type = "state_change"

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "new", self.state.status.value

class JobInfoEvent(ClientEvent):
    event_type = PrinterEvent.JOB_INFO.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in self.state.job_info.trait_values().items():
            if self.state.has_changed(self.state.job_info, key):
                yield key, value

# TODO in the future
class AiResponseEvent(ClientEvent):
    event_type = "ai_resp"

class PrinterErrorEvent(ClientEvent):
    event_type = "printer_error"

class ShutdownEvent(ClientEvent):
    event_type = "shutdown"

class StreamEvent(ClientEvent):
    event_type = "stream"

class LatencyEvent(ClientEvent):
    event_type = "latency"

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "ms", self.ping_pong.pong - self.ping_pong.ping

class FileProgressEvent(ClientEvent):
    event_type = "file_progress"

    def generate_data(self) -> Generator[Tuple, None, None]:
        """
        When a file progress event is triggered, always yield state, the two other fields 
        percent and message are optionally tied to respectfully downloading and error states.

        But since we always send the state you can update any other fields you want to send and still 
        achieve the same result.
        """
        yield "state", self.state.file_progress.state.value

        for key, value in self.state.file_progress.trait_values().items():
            if key == "state": continue
            if self.state.has_changed(self.state.file_progress, key):
                yield key, value

class FilamentSensorEvent(ClientEvent):
    event_type = "filament_sensor"

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "state", self.state.filament_sensor.state.value

class PowerControllerEvent(ClientEvent):
    event_type = PrinterEvent.PSU.value

    def generate_data(self) -> Generator[Tuple, None, None]:
        yield "on", self.state.psu_info.on

class CpuInfoEvent(ClientEvent):
    event_type = "cpu_info"

    def generate_data(self) -> Generator[Tuple, None, None]:
        for key, value in vars(self.state.cpu_info).get("_trait_values", dict()).items():
            if self.state.has_changed(self.state.cpu_info, key):
                yield key, value

class MeshDataEvent(ClientEvent):
    event_type = "mesh_data"

class LogsSentEvent(ClientEvent):
    event_type = "logs_sent"

