from enum import Enum
from typing import List, Optional, Union

from traitlets import Bool
from traitlets import Enum as TraitletsEnum
from traitlets import Float, Instance, Int, Integer
from traitlets import List as TraitletsList
from traitlets import Unicode, observe
from traitlets import Union as TraitletsUnion

from .always import Always
from .ambient_state import AmbientTemperatureState
from .state import State, ClientState, to_event
from .temperature import Temperature
from ..protocol.client_events import (
    CpuInfoEvent, FileProgressEvent, MachineDataEvent,
    FirmwareEvent,
    FirmwareWarningEvent, FilamentSensorEvent,
    PowerControllerEvent, JobInfoEvent, LatencyEvent,
    WebcamStatusEvent,
    WebcamEvent, MaterialDataEvent, StateChangeEvent,
    ConnectionEvent, ToolEvent)


class PrinterCpuFlag(Enum):
    NONE = 0
    THROTTLED = 1


@to_event(CpuInfoEvent)
class CpuInfoState(ClientState):
    usage: float = Float()
    temp: float = Float()
    memory: float = Float()


class PrinterStatus(Enum):
    OPERATIONAL = "operational"
    PRINTING = "printing"
    OFFLINE = "offline"
    PAUSED = "paused"
    PAUSING = "pausing"
    CANCELLING = "cancelling"
    RESUMING = "resuming"
    ERROR = "error"
    NOT_READY = "not_ready"


class FileProgressState(Enum):
    DOWNLOADING = "downloading"
    ERROR = "error"
    PENDING = "pending"
    STARTED = "started"
    READY = "ready"


@to_event(FileProgressEvent)
class PrinterFileProgressState(ClientState):
    state: Optional[FileProgressState] = Always(TraitletsEnum(FileProgressState, allow_none=True))
    percent: float = Float(default_value=0.0)
    message: Optional[str] = Unicode(allow_none=True)  # Typically error message


@to_event(MachineDataEvent)
class PrinterInfoData(ClientState):
    ui = Unicode(allow_none=True)
    ui_version = Unicode(allow_none=True)
    api = Unicode(allow_none=True)
    api_version = Unicode(allow_none=True)
    machine = Unicode(allow_none=True)
    os = Unicode(allow_none=True)
    sp_version = Unicode(allow_none=True)
    python_version = Unicode(allow_none=True)
    is_ethernet = Bool(allow_none=True)
    ssid = Unicode(allow_none=True)
    local_ip = Unicode(allow_none=True)
    hostname = Unicode(allow_none=True)
    core_count = Int(allow_none=True)
    total_memory = Int(allow_none=True)
    mac = Unicode(allow_none=True)


class PrinterDisplaySettings(ClientState):
    enabled: bool = Bool()
    branding: bool = Bool()
    while_printing_type: int = Int()
    show_status: bool = Bool()


class PrinterSettings(ClientState):
    has_psu: bool = Bool()
    has_filament_sensor: bool = Bool()


@to_event(FirmwareEvent)
class PrinterFirmware(ClientState):
    name: Optional[str] = Unicode(allow_none=True, default_value=None)
    name_raw: Optional[str] = Unicode(allow_none=True, default_value=None)
    machine: Optional[str] = Unicode(allow_none=True, default_value=None)
    machine_name: Optional[str] = Unicode(allow_none=True, default_value=None)
    version: Optional[str] = Unicode(allow_none=True, default_value=None)
    date: Optional[str] = Unicode(allow_none=True, default_value=None)
    link: Optional[str] = Unicode(allow_none=True, default_value=None)


@to_event(FirmwareWarningEvent)
class PrinterFirmwareWarning(ClientState):
    check_name: Optional[str] = Unicode()
    warning_type: Optional[str] = Unicode()
    severity: Optional[str] = Unicode()
    url: Optional[str] = Unicode()


class PrinterFilamentSensorEnum(Enum):
    LOADED = "loaded"
    RUNOUT = "runout"


@to_event(FilamentSensorEvent)
class PrinterFilamentSensorState(ClientState):
    state: Optional[PrinterFilamentSensorEnum] = TraitletsEnum(
        PrinterFilamentSensorEnum)


@to_event(PowerControllerEvent)
class PrinterPSUState(ClientState):
    on: bool = Bool()


@to_event(JobInfoEvent)
class JobInfoState(ClientState):
    progress: Optional[float] = Float()
    initial_estimate: Optional[float] = Float()
    layer: Optional[int] = Int()
    time: Optional[float] = Float()  # Time left in seconds
    filament: Optional[float] = Float()  # Filament usage
    filename: Optional[str] = Unicode(allow_none=True)
    delay: Optional[float] = Float()
    # Not yet implemented
    # ai: List[int] = TraitletsList(Int())

    started: bool = Always(Bool())
    finished: bool = Always(Bool())
    cancelled: bool = Always(Bool())
    failed: bool = Always(Bool())

    @observe("started", "finished", "cancelled", "failed")
    def _on_job_state_change(self, change):  # If one changes, set the others to false
        if not change["new"]:
            return

        for key in ["started", "finished", "cancelled", "failed"]:
            # Only set "True" values to "False"
            # As undefined values can stay undefined
            if key != change["name"] and getattr(self, key):
                setattr(self, key, False)


@to_event(LatencyEvent, "pong")
class PingPongState(ClientState):
    ping: Optional[float] = Float()  # Timestamp when ping was sent
    pong: Optional[float] = Float()  # Timestamp when pong was received


@to_event(WebcamStatusEvent, "connected")
class WebcamState(ClientState):
    connected: bool = Bool()


@to_event(WebcamEvent)
class WebcamSettings(ClientState):
    flipH: bool = Bool()
    flipV: bool = Bool()
    rotate90: bool = Bool()


@to_event(MaterialDataEvent)
class MaterialModel(ClientState):
    type: Optional[Union[str, int]] = TraitletsUnion([Int(), Unicode()], allow_none=True)
    color: Optional[str] = Unicode(None, allow_none=True)
    hex: Optional[str] = Unicode(None, allow_none=True)
    ext: Optional[int] = Integer(None, allow_none=True)


@to_event(StateChangeEvent, "status")
@to_event(ConnectionEvent, "connected")
@to_event(ToolEvent, "active_tool")
class PrinterState(State):
    status: PrinterStatus = TraitletsEnum(PrinterStatus, allow_none=True)
    current_display_message: Optional[str] = Unicode()

    bed_temperature: Temperature = Instance(Temperature)
    tool_temperatures: List[Temperature] = TraitletsList(Instance(Temperature))

    ambient_temperature: AmbientTemperatureState = Instance(
        AmbientTemperatureState)
    info: PrinterInfoData = Instance(PrinterInfoData)
    cpu_info: CpuInfoState = Instance(CpuInfoState)
    job_info: JobInfoState = Instance(JobInfoState)
    psu_info: PrinterPSUState = Instance(PrinterPSUState)
    settings: PrinterSettings = Instance(PrinterSettings)
    firmware: PrinterFirmware = Instance(PrinterFirmware)
    latency: PingPongState = Instance(PingPongState)
    webcam_info: WebcamState = Instance(WebcamState)
    display_settings: PrinterDisplaySettings = Instance(PrinterDisplaySettings)
    file_progress: PrinterFileProgressState = Instance(
        PrinterFileProgressState)
    filament_sensor: PrinterFilamentSensorState = Instance(
        PrinterFilamentSensorState)
    webcam_settings: WebcamSettings = Instance(WebcamSettings)

    active_tool: Optional[int] = Integer(None, allow_none=True)
    material_data: List[MaterialModel] = TraitletsList(Instance(MaterialModel, allow_none=True))

    def __init__(self, nozzle_count: int = 1, extruder_count: int = 1) -> None:
        super().__init__(
            # status starts as none, it is up to the client to set it
            status=None,
            bed_temperature=Temperature(),
            tool_temperatures=[Temperature() for _ in range(nozzle_count)],
            ambient_temperature=AmbientTemperatureState(),
            info=PrinterInfoData(),
            settings=PrinterSettings(),
            display_settings=PrinterDisplaySettings(),
            firmware=PrinterFirmware(),
            cpu_info=CpuInfoState(),
            webcam_info=WebcamState(),
            webcam_settings=WebcamSettings(),
            job_info=JobInfoState(),
            psu_info=PrinterPSUState(),
            latency=PingPongState(),
            file_progress=PrinterFileProgressState(state=None),
            filament_sensor=PrinterFilamentSensorState(),
            material_data=[MaterialModel() for _ in range(extruder_count)],
        )

    def set_nozzle_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("Nozzle count must be at least 1")

        if count > len(self.tool_temperatures):
            for _ in range(count - len(self.tool_temperatures)):
                self.tool_temperatures.append(model := Temperature())
                model.set_root_state(self)
        else:
            self.tool_temperatures = self.tool_temperatures[:count]

    def set_extruder_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("Extruder count must be at least 1")
        if self.active_tool is not None and self.active_tool >= count:
            self.active_tool = None

        if count > len(self.material_data):
            for _ in range(count - len(self.material_data)):
                self.material_data.append(model := MaterialModel())
                model.set_root_state(self)
        else:
            self.material_data = self.material_data[:count]

    def is_printing(self) -> bool:
        return self.status == PrinterStatus.PRINTING

    def is_heating(self) -> bool:
        for tool in self.tool_temperatures:
            if tool.is_heating():
                return True

        if self.bed_temperature is not None and self.bed_temperature.is_heating():
            return True

        return False
