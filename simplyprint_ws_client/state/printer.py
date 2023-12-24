from enum import Enum
from typing import List, Optional

from traitlets import Bool
from traitlets import Enum as TraitletsEnum
from traitlets import Float, Instance, Int, Integer
from traitlets import List as TraitletsList
from traitlets import Unicode, observe

from ..events.client_events import *
from ..helpers.ambient_check import AmbientTemperatureState
from ..helpers.intervals import Intervals
from ..helpers.temperature import Temperature
from .always import Always
from .models import MaterialModel
from .root_state import ClientState, RootState, to_event


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
    state: Optional[FileProgressState] = TraitletsEnum(FileProgressState)
    percent: Optional[float] = Float()
    message: Optional[str] = Unicode()  # Typically error message


@to_event(MachineDataEvent)
class PrinterInfoData(ClientState):
    ui = Unicode()
    ui_version = Unicode()
    api = Unicode()
    api_version = Unicode()
    machine = Unicode()
    os = Unicode()
    sp_version = Unicode()
    python_version = Unicode()
    is_ethernet = Bool()
    ssid = Unicode(allow_none=True)
    local_ip = Unicode()
    hostname = Unicode()
    core_count = Int()
    total_memory = Int()
    mac = Unicode()

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
    name: Optional[str] = Unicode()
    name_raw: Optional[str] = Unicode()
    version: Optional[str] = Unicode()
    date: Optional[str] = Unicode()
    link: Optional[str] = Unicode()


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
    filename: Optional[str] = Unicode()

    started: bool = Always(Bool())
    finished: bool = Always(Bool())
    cancelled: bool = Always(Bool())
    failed: bool = Always(Bool())

    @observe("started", "finished", "cancelled", "failed")
    def _on_job_state_change(self, change):        # If one changes, set the others to false
        if not change["new"]:
            return
        
        for key in ["started", "finished", "cancelled", "failed"]:
            # Only set "True" values to "False"
            # As undefined values can stay undefined
            if key != change["name"] and getattr(self, key):
                setattr(self, key, False)

    delay: Optional[float] = Float()

    # Not yet implemented
    # ai: List[int] = TraitletsList(Int())


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

@to_event(StateChangeEvent, "status")
@to_event(ConnectionEvent, "connected")
@to_event(ToolEvent, "active_tool")
@to_event(MaterialDataEvent, "material_data")
class PrinterState(RootState):
    status: PrinterStatus = TraitletsEnum(PrinterStatus)
    current_display_message: Optional[str] = Unicode()

    bed_temperature: Temperature = Instance(Temperature)
    tool_temperatures: List[Temperature] = TraitletsList(Instance(Temperature))

    ambient_temperature: AmbientTemperatureState = Instance(
        AmbientTemperatureState)
    
    intervals: Intervals = Instance(Intervals)

    info: PrinterInfoData = Instance(PrinterInfoData)
    cpu_info: CpuInfoState = Instance(CpuInfoState)
    job_info: JobInfoState = Instance(JobInfoState)
    psu_info: PrinterPSUState = Instance(PrinterPSUState)
    settings: PrinterSettings = PrinterSettings()
    firmware: PrinterFirmware = PrinterFirmware()
    ping_pong: PingPongState = Instance(PingPongState)
    webcam_info: WebcamState = Instance(WebcamState)
    display_settings: PrinterDisplaySettings = PrinterDisplaySettings()
    file_progress: PrinterFileProgressState = Instance(
        PrinterFileProgressState)
    filament_sensor: PrinterFilamentSensorState = Instance(
        PrinterFilamentSensorState)
    webcam_settings: WebcamSettings = Instance(WebcamSettings)

    active_tool: Optional[int] = Integer(None, allow_none=True)
    material_data: List[MaterialModel] = TraitletsList(Instance(MaterialModel))

    def __init__(self, extruder_count: int = 1) -> None:
        super().__init__(
            status=PrinterStatus.OFFLINE,
            bed_temperature=Temperature(),
            tool_temperatures=[Temperature() for _ in range(extruder_count)],
            ambient_temperature=AmbientTemperatureState(),
            intervals=Intervals(),
            info=PrinterInfoData(),
            settings=PrinterSettings(),
            display_settings=PrinterDisplaySettings(),
            firmware=PrinterFirmware(),
            cpu_info=CpuInfoState(),
            webcam_info=WebcamState(),
            webcam_settings=WebcamSettings(),
            job_info=JobInfoState(),
            psu_info=PrinterPSUState(),
            ping_pong=PingPongState(),
            file_progress=PrinterFileProgressState(),
            filament_sensor=PrinterFilamentSensorState(),
            material_data=[MaterialModel() for _ in range(extruder_count)],
        )

    def set_extruder_count(self, count: int) -> None:
        if count > len(self.tool_temperatures):
            for _ in range(count - len(self.tool_temperatures)):
                self.tool_temperatures.append(Temperature())
        else:
            self.tool_temperatures = self.tool_temperatures[:count]

        if self.active_tool is not None and self.active_tool >= count:
            self.active_tool = None

        if count > len(self.material_data) :
            for _ in range(count - len(self.material_data)):
                self.material_data.append(MaterialModel())
        else:
            self.material_data = self.material_data[:count]
       

    def is_heating(self) -> bool:
        for tool in self.tool_temperatures:
            if tool.is_heating():
                return True

        if self.bed_temperature is not None and self.bed_temperature.is_heating():
            return True

        return False
