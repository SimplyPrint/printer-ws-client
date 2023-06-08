from enum import Enum
from typing import Optional, List
from traitlets import Int, Unicode, Float, List as TraitletsList, Instance, Bool, Enum as TraitletsEnum, observe

from .helpers.temperature import Temperature
from .helpers.ambient_check import AmbientTemperatureState
from .state import DEFAULT_EVENT, RootState, ClientState
from .events.client_events import *

class PrinterCpuFlag(Enum):
    NONE = 0
    THROTTLED = 1


class CpuInfoState(ClientState):
    usage: float = Float()
    temp: float = Float()
    memory: float = Float()

    event_map = {
        DEFAULT_EVENT: CpuInfoEvent,
    }


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


class PrinterFileProgressState(ClientState):
    state: Optional[FileProgressState] = TraitletsEnum(FileProgressState)
    percent: Optional[float] = Float()
    message: Optional[str] = Unicode()  # Typically error message

    event_map = {
        DEFAULT_EVENT: FileProgressEvent,
    }


class PrinterMachineData(ClientState):
    ui = Unicode()
    ui_version = Unicode()
    api = Unicode()
    api_version = Unicode()
    machine = Unicode()
    os = Unicode()
    sp_version = Unicode()
    python_version = Unicode()
    is_ethernet = Bool()
    ssid = Unicode()
    local_ip = Unicode()
    hostname = Unicode()
    core_count = Int()
    total_memory = Int()
    mac = Unicode()

    event_map = {
        DEFAULT_EVENT: MachineDataEvent,
    }

class PrinterDisplaySettings(ClientState):
    enabled: bool = Bool()
    branding: bool = Bool()
    while_printing_type: int = Int()
    show_status: bool = Bool()


class PrinterSettings(ClientState):
    has_psu: bool = Bool()
    has_filament_sensor: bool = Bool()


class PrinterFirmware(ClientState):
    name: Optional[str] = Unicode()
    name_raw: Optional[str] = Unicode()
    version: Optional[str] = Unicode()
    date: Optional[str] = Unicode()
    link: Optional[str] = Unicode()

    event_map = {
        DEFAULT_EVENT: FirmwareEvent,
    }


class PrinterFirmwareWarning(ClientEvent):
    check_name: Optional[str] = Unicode()
    warning_type: Optional[str] = Unicode()
    severity: Optional[str] = Unicode()
    url: Optional[str] = Unicode()

    event_map = {
        DEFAULT_EVENT: FirmwareWarningEvent,
    }


class PrinterFilamentSensorEnum(Enum):
    LOADED = "loaded"
    RUNOUT = "runout"


class PrinterFilamentSensorState(ClientState):
    state: Optional[PrinterFilamentSensorEnum] = TraitletsEnum(
        PrinterFilamentSensorEnum)

    event_map = {
        DEFAULT_EVENT: FilamentSensorEvent,
    }


class PrinterPSUState(ClientState):
    on: bool = Bool()

    event_map = {
        DEFAULT_EVENT: PowerControllerEvent,
    }


class JobInfoState(ClientState):
    progress: Optional[float] = Float()
    initial_estimate: Optional[float] = Float()
    layer: Optional[int] = Int()
    time: Optional[float] = Float()  # Time left in seconds
    filament: Optional[float] = Float()  # Filament usage
    filename: Optional[str] = Unicode()

    started: bool = Bool()
    finished: bool = Bool()
    cancelled: bool = Bool()
    failed: bool = Bool()

    delay: Optional[float] = Float()

    # Not yet implemented
    # ai: List[int] = TraitletsList(Int())

    event_map = {
        DEFAULT_EVENT: JobInfoEvent,
    }


class PingPongState(ClientState):
    ping: Optional[float] = Float()  # Timestamp when ping was sent
    pong: Optional[float] = Float()  # Timestamp when pong was received

    event_map = {
        "pong": LatencyEvent,
    }


class WebcamState(ClientState):
    connected: bool = Bool()

    event_map = {
        "connected": WebcamStatusEvent,
    }


class WebcamSettings(ClientState):
    flipH: bool = Bool()
    flipV: bool = Bool()
    rotate90: bool = Bool()

    event_map = {
        DEFAULT_EVENT: WebcamEvent,
    }


class PrinterState(RootState):
    name = Unicode(allow_none=True)
    connected = Bool()
    in_setup = Bool()

    status: PrinterStatus = TraitletsEnum(PrinterStatus)
    current_display_message: Optional[str] = Unicode()

    ambient_temperature = Float()

    bed_temperature: Temperature = Instance(Temperature)
    tool_temperatures = TraitletsList(Instance(Temperature))

    ambient_temperature: AmbientTemperatureState = Instance(
        AmbientTemperatureState)

    machine_data: PrinterMachineData = Instance(PrinterMachineData)
    settings: PrinterSettings = PrinterSettings()
    display_settings: PrinterDisplaySettings = PrinterDisplaySettings()
    firmware: PrinterFirmware = PrinterFirmware()
    cpu_info: CpuInfoState = Instance(CpuInfoState)
    webcam_info: WebcamState = Instance(WebcamState)
    webcam_settings: WebcamSettings = Instance(WebcamSettings)
    job_info: JobInfoState = Instance(JobInfoState)
    psu_info: PrinterPSUState = Instance(PrinterPSUState)
    ping_pong: PingPongState = Instance(PingPongState)
    file_progress: PrinterFileProgressState = Instance(
        PrinterFileProgressState)
    filament_sensor: PrinterFilamentSensorState = Instance(
        PrinterFilamentSensorState)

    event_map = {
        "status": StateChangeEvent,
        "connected": ConnectionEvent,
    }

    def is_heating(self) -> bool:
        for tool in self.tool_temperatures:
            if tool.heating():
                return True

        if self.bed_temperature is not None and self.bed_temperature.heating():
            return True

        return False
