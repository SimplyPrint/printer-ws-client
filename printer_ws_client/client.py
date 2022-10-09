import asyncio
from concurrent.futures import Future
import logging
import json

from .printer_state import Printer, PrinterStatus, Temperature
from .connection import Connection
from .event import *
from .timer import Intervals
from .async_loop import AsyncLoop

from logging import Logger
from typing import List, Optional
from enum import Enum

class PrinterEvent(Enum):
    STATUS = "state_change"
    TEMPERATURES = "temps"
    SHUTDOWN = "shutdown"
    CONNECTION = "connection"
    CAMERA_SETTINGS = "camera_settings"
    GCODE_TERMINAL = "gcode_terminal"
    JOB_UPDATE = "job_update"
    PLUGIN_INSTALLED = "plugin_installed"
    PSU_CHANGE = "psu_change"
    MESH_DATA = "mesh_data"
    PRINT_STARTED = "print_started"
    PRINT_DONE = "print_done"
    PRINT_PAUSING = "print_pausing"
    PRINT_PAUSED = "print_paused"
    PRINT_CANCELLED = "print_cancelled"
    PRINT_FALIURE = "print_failure"
    PRINTER_ERROR = "printer_error"
    INPUT_REQUIRED = "input_required"
    UPDATE_STARTED = "update_started"
    UNSAFE_FIRMWARE = "unsafe_firmware"
    FILAMENT_ANALYSIS = "filament_analysis"
    OCTOPRINT_PLUGINS = "octoprint_plugins"

class Client:
    def __init__(self): 
        self.logger: Logger = logging.getLogger("simplyprint.client")

        self.callbacks: EventCallbacks = EventCallbacks() 

        self.connection: Connection = Connection(self.logger) 
        self.printer: Printer = Printer()
        self.intervals: Intervals = Intervals() 

        self.loop: AsyncLoop = AsyncLoop()
        self.process_task: Optional[Future[None]] = None

    # ---------- control ---------- #
 
    def start(self) -> None:
        self.loop.start() 
        self.process_task = self.loop.spawn(self.process_events())

    def stop(self) -> None:
        self.loop.stop()

    # ---------- client events ---------- #

    def set_id(self, id: str) -> None:
        self.connection.id = id

    def set_token(self, token: str) -> None:
        self.connection.token = token 

    def set_layer(self, layer: int) -> None:
        if self.printer.layer == layer:
            return

        self.printer.layer = layer

    def set_status(self, status: PrinterStatus) -> None:
        if self.printer.status == status:
            return

        if self.printer.status == PrinterStatus.CANCELLING:
            # TODO: something with print done!?
            # NOTE: this can't be right
            pass

        self.printer.status = status
        self.send(PrinterEvent.STATUS, {
            "new": status.value,
        })

    def set_temperatures(self, tools: List[Temperature], bed: Optional[Temperature] = None) -> None: 
        self.printer.tool_temperatures = tools
        self.printer.bed_temperature = bed

        if self.intervals.temperatures_updating:
            return

        self.intervals.temperatures_updating = True
        self.loop.spawn(self.send_temperatures())

    async def send_temperatures(self) -> None:
        await self.intervals.sleep_until_temperatures()
        payload = {}

        

        self.logger.debug(f"Sending temperatures: {payload}")
        await self.send_async(PrinterEvent.TEMPERATURES, payload)
        self.intervals.temperatures_updating = False

    # ---------- io ---------- #

    def send(self, event: PrinterEvent, data: Any) -> Future[None]:
        return self.loop.spawn(self.send_async(event, data))

    async def send_async(self, event: PrinterEvent, data: Any) -> None:
        message = json.dumps({
            "type": event.value,
            "data": data,
        })
        await self.send_message_async(message)

    def send_message(self, message: str) -> None:
        self.loop.spawn(self.send_message_async(message))

    async def connect(self):
        while not self.connection.is_connected():
            if self.intervals.reconnect_updating:
                await asyncio.sleep(1.0) # TODO: this is a hack
                continue

            self.intervals.reconnect_updating = True
            await self.intervals.sleep_until_reconnect()
            await self.connection.connect()
            self.intervals.reconnect_updating = False

    async def send_message_async(self, message: str) -> None:
        await self.connect()
        await self.connection.send_message(message)

    # ---------- server events ---------- #

    async def process_events(self):
        while True:
            await self.connect()

            event = await self.connection.read_event()

            if event is None:
                self.logger.error("invalid event")
                continue

            self.handle_event(event)

    def handle_event(self, event: Event) -> None:
        self.callbacks.on_event(event)

        if isinstance(event, NewTokenEvent):
            self.handle_new_token_event(event)
        elif isinstance(event, ConnectEvent):
            self.handle_connect_event(event)
        elif isinstance(event, SetupCompleteEvent):
            self.handle_setup_complete_event(event)
        elif isinstance(event, IntervalChangeEvent):
            self.handle_interval_change_event(event)
        elif isinstance(event, PongEvent):
            self.handle_pong_event(event)
        elif isinstance(event, StreamReceivedEvent):
            self.handle_stream_received_event(event)
        elif isinstance(event, PrinterSettingsEvent):
            self.handle_printer_settings_event(event)
        elif isinstance(event, PauseEvent):
            self.handle_pause_event(event)
        elif isinstance(event, ResumeEvent):
            self.handle_resume_event(event)
        elif isinstance(event, CancelEvent):
            self.handle_cancel_event(event)
        elif isinstance(event, TerminalEvent):
            self.handle_terminal_event(event)
        elif isinstance(event, GcodeEvent):
            self.handle_gcode_event(event)
        elif isinstance(event, WebcamTestEvent):
            self.handle_webcam_test_event(event)
        elif isinstance(event, WebcamSnapshotEvent):
            self.handle_webcam_snapshot_event(event)
        elif isinstance(event, FileEvent):
            self.handle_file_event(event)
        elif isinstance(event, StartPrintEvent):
            self.handle_start_print_event(event)
        elif isinstance(event, ConnectPrinterEvent):
            self.handle_connect_printer_event(event)
        elif isinstance(event, DisconnectPrinterEvent):
            self.handle_disconnect_printer_event(event)
        elif isinstance(event, SystemRestartEvent):
            self.handle_system_restart_event(event)
        elif isinstance(event, SystemShutdownEvent):
            self.handle_system_shutdown_event(event)
        elif isinstance(event, ApiRestartEvent):
            self.handle_api_restart_event(event)
        elif isinstance(event, ApiShutdownEvent):
            self.handle_api_shutdown_event(event)
        elif isinstance(event, UpdateEvent):
            self.handle_update_event(event)
        elif isinstance(event, PluginInstallEvent):
            self.handle_plugin_install_event(event)
        elif isinstance(event, PluginUninstallEvent):
            self.handle_plugin_uninstall_event(event)
        elif isinstance(event, WebcamSettingsEvent):
            self.handle_webcam_settings_event(event)
        elif isinstance(event, StreamOnEvent):
            self.handle_stream_on_event(event)
        elif isinstance(event, StreamOffEvent):
            self.handle_stream_off_event(event)
        elif isinstance(event, SetPrinterProfileEvent):
            self.handle_set_printer_profile_event(event)
        elif isinstance(event, GetGcodeScriptBackupsEvent):
            self.handle_get_gcode_script_backups_event(event)
        elif isinstance(event, HasGcodeChangesEvent):
            self.handle_has_gcode_changes_event(event)
        elif isinstance(event, PsuControlEvent):
            self.handle_psu_control_event(event)
        elif isinstance(event, DisableWebsocketEvent):
            self.handle_disable_websocket_event(event)
     
    # ---------- event handlers ---------- #

    def handle_error_event(self, event: ErrorEvent) -> None:
        self.logger.error(f"Error: {event.error}")

        self.intervals.reconnect = 30.0
        self.connection.reconnect_token = None

        self.callbacks.on_error(event)
            
    def handle_new_token_event(self, event: NewTokenEvent) -> None:
        self.logger.info(f"Received new token: {event.token} short id: {event.short_id}")

        self.connection.id = event.short_id
        self.connection.token = event.token

        if event.no_exist:
            self.printer.is_set_up = False

        self.callbacks.on_new_token(event)

    def handle_connect_event(self, event: ConnectEvent) -> None:
        self.logger.info(f"Connected to server")

        self.intervals.update(event.intervals)
        self.printer.connected = True
        self.printer.name = event.name
        self.connection.reconnect_token = event.reconnect_token

        self.callbacks.on_connect(event)

    def handle_setup_complete_event(self, event: SetupCompleteEvent) -> None:
        self.logger.info(f"Setup complete")

        self.connection.id = event.printer_id
        self.printer.is_set_up = True

        self.callbacks.on_setup_complete(event)

    def handle_interval_change_event(self, event: IntervalChangeEvent) -> None:
        self.logger.info(f"Interval change")

        self.intervals.update(event.intervals)
        self.callbacks.on_interval_change(event)

    def handle_pong_event(self, event: PongEvent) -> None:
        self.logger.info(f"Pong")

        self.callbacks.on_pong(event)

    def handle_stream_received_event(self, event: StreamReceivedEvent) -> None:
        self.logger.info(f"Stream received")

        self.callbacks.on_stream_received(event)

    def handle_printer_settings_event(self, event: PrinterSettingsEvent) -> None:
        self.logger.info(f"Printer settings")

        self.callbacks.on_printer_settings(event)

    def handle_pause_event(self, event: PauseEvent) -> None:
        self.logger.info(f"Pause")

        self.callbacks.on_pause(event)

    def handle_resume_event(self, event: ResumeEvent) -> None:
        self.logger.info(f"Resume")

        self.callbacks.on_resume(event)

    def handle_cancel_event(self, event: CancelEvent) -> None:
        self.logger.info(f"Cancel")

        self.callbacks.on_cancel(event)

    def handle_terminal_event(self, event: TerminalEvent) -> None:
        self.logger.info(f"Terminal")

        self.callbacks.on_terminal(event)

    def handle_gcode_event(self, event: GcodeEvent) -> None:
        self.logger.info(f"Gcode")

        self.callbacks.on_gcode(event)

    def handle_webcam_test_event(self, event: WebcamTestEvent) -> None:
        self.logger.info(f"Webcam test")

        self.callbacks.on_webcam_test(event)

    def handle_webcam_snapshot_event(self, event: WebcamSnapshotEvent) -> None:
        self.logger.info(f"Webcam snapshot")

        self.callbacks.on_webcam_snapshot(event)

    def handle_file_event(self, event: FileEvent) -> None:
        self.logger.info(f"File")

        self.callbacks.on_file(event)

    def handle_start_print_event(self, event: StartPrintEvent) -> None:
        self.logger.info(f"Start print")

        self.callbacks.on_start_print(event)

    def handle_connect_printer_event(self, event: ConnectPrinterEvent) -> None:
        self.logger.info(f"Connect printer")

        self.callbacks.on_connect_printer(event)

    def handle_disconnect_printer_event(self, event: DisconnectPrinterEvent) -> None:
        self.logger.info(f"Disconnect printer")

        self.callbacks.on_disconnect_printer(event)

    def handle_system_restart_event(self, event: SystemRestartEvent) -> None:
        self.logger.info(f"System restart")

        self.callbacks.on_system_restart(event)

    def handle_system_shutdown_event(self, event: SystemShutdownEvent) -> None:
        self.logger.info(f"System shutdown")

        self.callbacks.on_system_shutdown(event)

    def handle_api_restart_event(self, event: ApiRestartEvent) -> None:
        self.logger.info(f"API restart")

        self.callbacks.on_api_restart(event)

    def handle_api_shutdown_event(self, event: ApiShutdownEvent) -> None:
        self.logger.info(f"API shutdown")

        self.callbacks.on_api_shutdown(event)

    def handle_update_event(self, event: UpdateEvent) -> None:
        self.logger.info(f"Update")

        self.callbacks.on_update(event)

    def handle_plugin_install_event(self, event: PluginInstallEvent) -> None:
        self.logger.info(f"Plugin install")

        self.callbacks.on_plugin_install(event)

    def handle_plugin_uninstall_event(self, event: PluginUninstallEvent) -> None:
        self.logger.info(f"Plugin uninstall")

        self.callbacks.on_plugin_uninstall(event)

    def handle_webcam_settings_event(self, event: WebcamSettingsEvent) -> None:
        self.logger.info(f"Webcam settings")

        self.callbacks.on_webcam_settings(event)

    def handle_stream_on_event(self, event: StreamOnEvent) -> None:
        self.logger.info(f"Stream on")

        self.callbacks.on_stream_on(event)

    def handle_stream_off_event(self, event: StreamOffEvent) -> None:
        self.logger.info(f"Stream off")

        self.callbacks.on_stream_off(event)

    def handle_set_printer_profile_event(self, event: SetPrinterProfileEvent) -> None:
        self.logger.info(f"Set printer profile")

        self.callbacks.on_set_printer_profile(event)

    def handle_get_gcode_script_backups_event(self, event: GetGcodeScriptBackupsEvent) -> None:
        self.logger.info(f"Get gcode script backups")

        self.callbacks.on_get_gcode_script_backups(event)

    def handle_has_gcode_changes_event(self, event: HasGcodeChangesEvent) -> None:
        self.logger.info(f"Has gcode changes")

        self.callbacks.on_has_gcode_changes(event)

    def handle_psu_control_event(self, event: PsuControlEvent) -> None:
        self.logger.info(f"PSU control")

        self.callbacks.on_psu_control(event)

    def handle_disable_websocket_event(self, event: DisableWebsocketEvent) -> None:
        self.logger.info(f"Disable websocket")

        self.callbacks.on_disable_websocket(event)

