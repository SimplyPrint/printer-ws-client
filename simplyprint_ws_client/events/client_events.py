from enum import Enum
from typing import Any, Dict, Generator, Optional, Tuple, TYPE_CHECKING, Union, Callable, List

from ..events.event import Event
from ..helpers.intervals import IntervalTypes, IntervalTypeRef, IntervalException

if TYPE_CHECKING:
    from ..client import Client
    from ..state.printer import PrinterState


class PrinterEvent(Enum):
    PING = "ping"
    KEEPALIVE = "keepalive"
    LATENCY = "latency"
    TOOL = "tool"
    STATUS = "state_change"
    AMBIENT = "ambient"
    TEMPERATURES = "temps"
    SHUTDOWN = "shutdown"
    CONNECTION = "connection"
    CAMERA_SETTINGS = "camera_settings"
    JOB_INFO = "job_info"
    FILE_PROGRESS = "file_progress"
    PSU_CHANGE = "psu_change"
    CPU_INFO = "cpu_info"
    PSU = "power_controller"
    STREAM = "stream"
    PRINTER_ERROR = "printer_error"
    MESH_DATA = "mesh_data"
    INFO = "machine_data"
    INPUT_REQUIRED = "input_required"
    UPDATE_STARTED = "update_started"
    FIRMWARE = "firmware"
    WEBCAM = "webcam"
    WEBCAM_STATUS = "webcam_status"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"
    GCODE_SCRIPTS = "gcode_scripts"
    INSTALLED_PLUGINS = "installed_plugins"
    SOFTWARE_UPDATES = "software_updates"
    FIRMWARE_WARNING = "firmware_warning"
    AI_RESP = "ai_resp"
    LOGS_SENT = "logs_sent"
    FILAMENT_SENSOR = "filament_sensor"
    MATERIAL_DATA = "material_data"

    def is_allowed_in_setup(self) -> bool:
        return self in [
            PrinterEvent.PING,
            PrinterEvent.KEEPALIVE,
            PrinterEvent.CONNECTION,
            PrinterEvent.STATUS,
            PrinterEvent.SHUTDOWN,
            PrinterEvent.INFO,
            PrinterEvent.FIRMWARE,
            PrinterEvent.FIRMWARE_WARNING,
            PrinterEvent.INSTALLED_PLUGINS,
        ]


class ClientEventMode(Enum):
    DISPATCH = 0
    RATELIMIT = 1
    CANCEL = 2


class ClientEvent(Event):
    event_type: PrinterEvent
    interval_type: Optional[IntervalTypeRef] = None

    _on_sent_hooks: List[Callable]
    for_client: Optional[Union[str, int]] = None
    data: Optional[Dict[str, Any]] = None

    def __init__(
            self,
            data: Optional[Union[Dict[str, Any], Generator[Tuple[str, Any, Optional[Callable]], None, None]]] = None,
            for_client: Optional[Union[str, int]] = None
    ) -> None:
        """
        for_client: id of client event belongs to
        data (Optional[Dict[str, Any]], optional): Custom data to send with the event. Defaults to None.
        """
        self._on_sent_hooks = []
        self.for_client = for_client

        if data is None:
            return

        if isinstance(data, dict):
            self.data = data
            return

        self.data = dict()

        for key, value, callback in data:
            self.data[key] = value

            if callback is not None:
                self._on_sent_hooks.append(callback)

    def generate(self) -> Generator[Tuple[str, Any], None, None]:
        yield "type", self.get_name()

        if self.for_client is not None and self.for_client != 0:
            yield "for", self.for_client

        if self.data is not None:
            yield "data", self.data

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.generate())

    def get_interval_type(self, client: "Client") -> Optional[IntervalTypeRef]:
        return self.interval_type

    def get_client_mode(self, client: "Client") -> ClientEventMode:
        if interval_type_ref := self.get_interval_type(client):
            interval_type = IntervalTypes.from_any(interval_type_ref)

            try:
                client.intervals.use(interval_type)
            except IntervalException:
                return ClientEventMode.RATELIMIT

        return ClientEventMode.DISPATCH

    def on_sent(self) -> None:
        while len(self._on_sent_hooks) > 0:
            self._on_sent_hooks.pop()()

    @classmethod
    def get_name(cls) -> Optional[str]:
        if cls is ClientEvent:
            return ClientEvent.__name__

        return cls.event_type.value

    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs) -> "ClientEvent":
        return cls(data, **kwargs)

    @classmethod
    def from_state(cls, state: "PrinterState", **kwargs) -> "ClientEvent":
        return cls(cls.build(state), **kwargs)

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple[str, Any, Optional[Callable]], None, None]:
        ...


class GcodeScriptsEvent(ClientEvent):
    event_type = PrinterEvent.GCODE_SCRIPTS


class MachineDataEvent(ClientEvent):
    event_type = PrinterEvent.INFO

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in state.info.trait_values().items():
            yield key, value, state.info.partial_clear(key)


class WebcamStatusEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM_STATUS

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "connected", state.webcam_info.connected, state.webcam_info.partial_clear("connected")


class WebcamEvent(ClientEvent):
    event_type = PrinterEvent.WEBCAM

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in state.webcam_settings.trait_values().items():
            if state.webcam_settings.has_changed(key):
                yield key, value, state.webcam_settings.partial_clear(key)


class InstalledPluginsEvent(ClientEvent):
    event_type = PrinterEvent.INSTALLED_PLUGINS


class SoftwareUpdatesEvent(ClientEvent):
    event_type = PrinterEvent.SOFTWARE_UPDATES


class FirmwareEvent(ClientEvent):
    event_type = PrinterEvent.FIRMWARE

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in state.firmware.trait_values().items():
            if state.firmware.has_changed(key):
                yield f"firmware_{key}", value, state.firmware.partial_clear(key)


class FirmwareWarningEvent(ClientEvent):
    event_type = PrinterEvent.FIRMWARE_WARNING

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in state.firmware.trait_values().items():
            yield key, value, state.firmware.partial_clear(key)


class ToolEvent(ClientEvent):
    event_type = PrinterEvent.TOOL

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "new", state.active_tool, state.partial_clear("active_tool")


class TemperatureEvent(ClientEvent):
    event_type = PrinterEvent.TEMPERATURES
    interval_type = IntervalTypes.TEMPS

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        if state.bed_temperature.has_changed():
            yield "bed", state.bed_temperature.to_list(), state.bed_temperature.partial_clear()

        for i, tool in enumerate(state.tool_temperatures):
            if tool.has_changed():
                yield f"tool{i}", tool.to_list(), tool.partial_clear()

    def get_interval_type(self, client: "Client") -> Optional[IntervalTypeRef]:
        state = client.printer

        # If we have a target temperature, send it more often (use IntervalTypes.TEMPS_TARGET)
        if state.bed_temperature.target is not None or any(
                [tool.target is not None for tool in state.tool_temperatures]):
            return IntervalTypes.TEMPS_TARGET

        return IntervalTypes.TEMPS


class AmbientTemperatureEvent(ClientEvent):
    event_type = PrinterEvent.AMBIENT

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "new", round(state.ambient_temperature.ambient), state.ambient_temperature.partial_clear()


class ConnectionEvent(ClientEvent):
    event_type = PrinterEvent.CONNECTION


class StateChangeEvent(ClientEvent):
    event_type = PrinterEvent.STATUS

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "new", state.status.value, state.partial_clear("status")


class JobInfoEvent(ClientEvent):
    event_type = PrinterEvent.JOB_INFO
    interval_type = IntervalTypes.JOB

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in state.job_info.trait_values().items():
            if state.job_info.has_changed(key):
                if key in ["started", "finished", "cancelled", "failed"]:
                    # Only send updates in terms of true, since they
                    # are mutually exclusive.
                    if not value:
                        continue

                # Do not send filename if it is None
                if key == "filename" and value is None:
                    continue

                yield key, value if key != 'progress' else round(value), state.job_info.partial_clear(key)


# TODO in the future
class AiResponseEvent(ClientEvent):
    event_type = PrinterEvent.AI_RESP


class PrinterErrorEvent(ClientEvent):
    event_type = PrinterEvent.PRINTER_ERROR


class ShutdownEvent(ClientEvent):
    event_type = PrinterEvent.SHUTDOWN


class StreamEvent(ClientEvent):
    event_type = PrinterEvent.STREAM
    interval_type = IntervalTypes.WEBCAM

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        # Stream events are not generated by the state, but are constructed
        # manually.
        raise NotImplementedError()


class PingEvent(ClientEvent):
    event_type = PrinterEvent.PING
    interval_type = IntervalTypes.PING


class LatencyEvent(ClientEvent):
    event_type = PrinterEvent.LATENCY

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "ms", state.latency.ping - state.latency.pong, state.latency.partial_clear("ping", "pong")


class FileProgressEvent(ClientEvent):
    event_type = PrinterEvent.FILE_PROGRESS

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        """
        When a file progress event is triggered, always yield state, the two other fields 
        percent and message are optionally tied to respectfully downloading and error states.

        But since we always send the state you can update any other fields you want to send and still 
        achieve the same result.

        TODO: Make enum accessible beyond circular import so we do not have to use literals.
        """
        yield "state", state.file_progress.state.value, state.file_progress.partial_clear("state")

        if state.file_progress.state.value == "error":
            yield "message", state.file_progress.message or "Unknown error", state.file_progress.partial_clear(
                "message")
            return

        # Only send percent as a field if we are downloading.
        if state.file_progress.state.value == "downloading" and state.file_progress.has_changed("percent"):
            yield "percent", state.file_progress.percent, state.file_progress.partial_clear("percent")


class FilamentSensorEvent(ClientEvent):
    event_type = PrinterEvent.FILAMENT_SENSOR

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "state", state.filament_sensor.state, state.filament_sensor.partial_clear()


class PowerControllerEvent(ClientEvent):
    event_type = PrinterEvent.PSU

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        yield "on", state.psu_info.on, state.psu_info.partial_clear()


class CpuInfoEvent(ClientEvent):
    event_type = PrinterEvent.CPU_INFO
    interval_type = IntervalTypes.CPU

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        for key, value in vars(state.cpu_info).get("_trait_values", dict()).items():
            if state.cpu_info.has_changed(key):
                yield key, value, state.cpu_info.partial_clear(key)


class MeshDataEvent(ClientEvent):
    event_type = PrinterEvent.MESH_DATA


class LogsSentEvent(ClientEvent):
    event_type = PrinterEvent.LOGS_SENT


class MaterialDataEvent(ClientEvent):
    event_type = PrinterEvent.MATERIAL_DATA
    has_changes = False

    @classmethod
    def build(cls, state: "PrinterState") -> Generator[Tuple, None, None]:
        if state.has_changed("material_data"):
            if len(state.material_data) == 0:
                return

            yield "materials", [material.trait_values() if material is not None else material for material in
                                state.material_data], state.partial_clear("material_data")
