__all__ = [
    'StateModel',
    'TemperatureState',
    'AmbientTemperatureState',
    'FileProgressState',
    'CpuInfoState',
    'PrinterInfoState',
    'PrinterFirmwareState',
    'PrinterFirmwareWarning',
    'PrinterFilamentSensorState',
    'PSUState',
    'JobInfoState',
    'PingPongState',
    'WebcamState',
    'WebcamSettings',
    'MaterialState',
    'PrinterState',
    'PrinterCpuFlag',
    'PrinterStatus',
    'FileProgressStateEnum',
    'FilamentSensorEnum',
    'Intervals',
    'DisplaySettings',
    'PrinterSettings',
]

from typing import Optional, Literal, no_type_check, Union, List, Set, ClassVar

import time
from pydantic import Field, PrivateAttr

from .exclusive import Exclusive
from .models import *
from .state_model import StateModel
from ..config import PrinterConfig
from ...const import VERSION
from ...shared.hardware.physical_machine import PhysicalMachine
from ...shared.sp.ambient_check import AmbientCheck


class TemperatureState(StateModel):
    actual: Optional[float] = None
    target: Optional[float] = None

    def as_rounded(self, k: Literal['actual', 'target']) -> Optional[int]:
        value: Optional[float] = getattr(self, k)

        if value is None:
            return None

        return round(value)

    def is_heating(self) -> bool:
        target = self.as_rounded('target')
        actual = self.as_rounded('actual')
        return target not in {None, 0} and target != actual

    def to_list(self):
        actual = self.as_rounded('actual')
        target = self.as_rounded('target')

        return [actual] + ([target] if target is not None else [])

    def __eq__(self, other):
        if not isinstance(other, TemperatureState):
            return False

        return self.as_rounded('target') == other.as_rounded('target') and self.as_rounded(
            'actual') == other.as_rounded('actual')


class AmbientTemperatureState(StateModel):
    ambient: int = 0

    _initial_sample: Optional[float] = None
    _update_interval: float = AmbientCheck.CHECK_INTERVAL
    _last_update: float = PrivateAttr(default_factory=lambda: time.time())

    def on_changed(self, new_ambient: float):
        self.ambient = round(new_ambient)

    def tick(
            self,
            state: 'PrinterState'
    ):
        """
        It is up to the implementation to decide when to invoke the check or respect the update_interval,
        the entire state is self-contained and requires the tool_temperatures to be passed in from the PrinterState,
        but it handles triggering the appropriate events.
        """
        now = time.time()

        if self._last_update is not None and now - self._last_update < self._update_interval:
            return

        self._last_update = now

        (self._initial_sample, self.ambient, self._update_interval) = AmbientCheck.detect(
            self.on_changed,
            state.tool_temperatures,
            self._initial_sample,
            self.ambient,
            state.status,
        )


class FileProgressState(StateModel):
    state: Optional[FileProgressStateEnum] = None
    percent: float = 0.0
    message: Optional[str] = None

    @no_type_check
    def __setattr__(self, key, value):
        super().__setattr__(key, value)

        # Reset the progress when the state changes away from downloading.
        if key == 'state' and value != FileProgressStateEnum.DOWNLOADING:
            self.percent = 0.0


class CpuInfoState(StateModel):
    usage: Optional[float] = None
    temp: Optional[float] = None
    memory: Optional[float] = None


class PrinterInfoState(StateModel):
    ui: Optional[str] = None
    ui_version: Optional[str] = None
    api: Optional[str] = None
    api_version: Optional[str] = None
    machine: Optional[str] = None
    os: Optional[str] = None
    sp_version: Optional[str] = VERSION
    python_version: Optional[str] = None
    is_ethernet: Optional[bool] = None
    ssid: Optional[str] = None
    local_ip: Optional[str] = None
    hostname: Optional[str] = None
    core_count: Optional[int] = None
    total_memory: Optional[int] = None
    mac: Optional[str] = None


class PrinterFirmwareState(StateModel):
    name: Optional[str] = None
    name_raw: Optional[str] = None
    machine: Optional[str] = None
    machine_name: Optional[str] = None
    version: Optional[str] = None
    date: Optional[str] = None
    link: Optional[str] = None


class PrinterFirmwareWarning(StateModel):
    check_name: Optional[str] = None
    warning_type: Optional[str] = None
    severity: Optional[str] = None
    url: Optional[str] = None


class PrinterFilamentSensorState(StateModel):
    state: Optional[FilamentSensorEnum] = None


class PSUState(StateModel):
    on: bool = False


class JobInfoState(StateModel, validate_assignment=True):
    progress: Optional[float] = None
    initial_estimate: Optional[float] = None
    layer: Optional[int] = None
    time: Optional[float] = None
    filament: Optional[float] = None
    filename: Optional[Exclusive[str]] = None
    delay: Optional[float] = None
    # Deprecated.
    # ai: List[int]

    # These needs to always trigger a reset.
    started: Exclusive[bool] = Field(default_factory=lambda: Exclusive[bool](False))
    finished: Exclusive[bool] = Field(default_factory=lambda: Exclusive[bool](False))
    cancelled: Exclusive[bool] = Field(default_factory=lambda: Exclusive[bool](False))
    failed: Exclusive[bool] = Field(default_factory=lambda: Exclusive[bool](False))

    # Mark a print job as a reprint of a previous (not-cleared) job from the client.
    reprint: Optional[Exclusive[int]] = None

    MUTUALLY_EXCLUSIVE_FIELDS: ClassVar[Set[str]] = {'started', 'finished', 'cancelled', 'failed'}

    @no_type_check
    def __setattr__(self, key, value):
        """Only one of the 4 fields can be True at a time."""
        if key not in self.MUTUALLY_EXCLUSIVE_FIELDS:
            return super().__setattr__(key, value)

        # Set all other to false
        for field in self.MUTUALLY_EXCLUSIVE_FIELDS - {key}:
            super().__setattr__(field, False)

        return super().__setattr__(key, value)


class PingPongState(StateModel):
    ping: Optional[float] = None
    pong: Optional[float] = None

    def ping_now(self):
        self.ping = time.monotonic()

    def pong_now(self):
        self.pong = time.monotonic()

    def get_latency(self) -> Optional[float]:
        if self.ping is None or self.pong is None:
            return None

        return round((self.pong - self.ping) * 1000)


class WebcamState(StateModel):
    connected: bool = False


class WebcamSettings(StateModel):
    flipH: bool = False
    flipV: bool = False
    rotate90: bool = False


class MaterialState(StateModel):
    type: Union[str, int, None] = None
    color: Optional[str] = None
    hex: Optional[str] = None
    ext: Optional[int] = None


class PrinterState(StateModel):
    config: PrinterConfig
    intervals: Intervals = Field(default_factory=Intervals)

    status: Optional[PrinterStatus] = None
    info: PrinterInfoState = Field(default_factory=PrinterInfoState)
    cpu_info: CpuInfoState = Field(default_factory=CpuInfoState)
    job_info: JobInfoState = Field(default_factory=JobInfoState)
    psu_info: PSUState = Field(default_factory=PSUState)
    webcam_info: WebcamState = Field(default_factory=WebcamState)
    file_progress: FileProgressState = Field(default_factory=FileProgressState)
    latency: PingPongState = Field(default_factory=PingPongState)

    firmware: PrinterFirmwareState = Field(default_factory=PrinterFirmwareState)
    firmware_warning: PrinterFirmwareWarning = Field(default_factory=PrinterFirmwareWarning)

    active_tool: Optional[int] = None
    material_data: List[MaterialState] = Field(default_factory=list)
    filament_sensor: PrinterFilamentSensorState = Field(default_factory=PrinterFilamentSensorState)

    bed_temperature: TemperatureState = Field(default_factory=TemperatureState)
    tool_temperatures: List[TemperatureState] = Field(default_factory=list)
    ambient_temperature: AmbientTemperatureState = Field(default_factory=AmbientTemperatureState)

    settings: PrinterSettings = Field(default_factory=PrinterSettings)
    webcam_settings: WebcamSettings = Field(default_factory=WebcamSettings)

    def set_info(self, name, version="0.0.1"):
        """ Set same info for all fields, both for UI / API and the client. """
        self.set_api_info(name, version)
        self.set_ui_info(name, version)

    def set_api_info(self, api: str, api_version: str):
        self.info.api = api
        self.info.api_version = api_version

    def set_ui_info(self, ui: str, ui_version: str):
        self.info.ui = ui
        self.info.ui_version = ui_version

    def set_nozzle_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("Nozzle count must be at least 1")

        if len(self.tool_temperatures) == count:
            return

        if count > len(self.tool_temperatures):
            for _ in range(count - len(self.tool_temperatures)):
                self.tool_temperatures.append(model := TemperatureState())
                model.provide_context(self)
        else:
            self.tool_temperatures = self.tool_temperatures[:count]

    def set_extruder_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("Extruder count must be at least 1")

        if self.active_tool is not None and self.active_tool >= count:
            self.active_tool = None

        if len(self.material_data) == count:
            return

        if count > len(self.material_data):
            for _ in range(count - len(self.material_data)):
                self.material_data.append(model := MaterialState())
                model.provide_context(self)
        else:
            self.material_data = self.material_data[:count]

    def is_printing(self, *status) -> bool:
        """If any of the statuses are printing, return True. Default behavior is to check own status."""
        if len(status) == 0:
            status = (self.status,)

        return PrinterStatus.is_printing(*status)

    def is_heating(self) -> bool:
        return any([tool.is_heating() for tool in (self.bed_temperature, *self.tool_temperatures)])

    def populate_info_from_physical_machine(self, *skip: str):
        """Set information about the physical machine the client is running on."""
        for k, v in PhysicalMachine.get_info().items():
            if k in skip:
                continue

            setattr(self.info, k, v)

    def mark_common_fields_as_changed(self):
        # Mark non-default fields as changed so they will be sent to the client.
        # In theory, we could store this information, but this is easier.
        self.model_set_changed('status')
        self.info.model_set_changed('sp_version')
        self.firmware.model_set_changed('name')
