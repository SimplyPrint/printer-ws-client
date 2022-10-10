import asyncio
import logging
import json
import copy

from concurrent.futures import Future
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
    callbacks: EventCallbacks = EventCallbacks() 
    __logger: Logger = logging.getLogger("simplyprint.client")

    should_close: bool = False

    connection: Connection = Connection(logging.getLogger("simplyprint.client.connection"))
    printer: Printer = Printer()
    intervals: Intervals = Intervals() 

    loop: AsyncLoop = AsyncLoop()
    process_task: Optional[Future[None]] = None 

    # ---------- control ---------- # 
    
    def start(self) -> None:
        self.loop.start() 
        self.process_task = self.loop.spawn(self.process_events())

    
    def stop(self) -> None:
        self.loop.stop() 

    # ---------- client events ---------- # 

    @property
    def id(self) -> Optional[str]:
        return self.connection.id

    @id.setter
    def id(self, id: str) -> None:
        self.connection.id = id

    @property
    def token(self) -> Optional[str]:
        return self.connection.token
    
    @token.setter
    def token(self, token: str) -> None:
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

    @property
    def tool_temperatures(self) -> List[Temperature]:
        return self.printer.tool_temperatures

    @tool_temperatures.setter
    def tool_temperatures(self, temperatures: List[Temperature]) -> None:
        self.printer.tool_temperatures = temperatures

        if self.intervals.temperatures_updating:
            return

        self.intervals.temperatures_updating = True
        self.loop.spawn(self.send_temperatures())

    @property
    def bed_temperature(self) -> Optional[Temperature]:
        return self.printer.bed_temperature
    
    @bed_temperature.setter
    def bed_temperature(self, temperature: Temperature) -> None:
        self.printer.bed_temperature = temperature

        if self.intervals.temperatures_updating:
            return

        self.intervals.temperatures_updating = True
        self.loop.spawn(self.send_temperatures()) 
    
    async def send_temperatures(self) -> None:
        await self.intervals.sleep_until_temperatures()
        payload = {}

        # TODO: this is virtually unreadable, clean it up
        if not self.printer.bed_temperature is None:
            if self.printer.server_bed_temperature is None: 
                payload["bed"] = self.printer.bed_temperature.to_list()
            else:
                if self.printer.server_bed_temperature.to_list() != self.printer.bed_temperature.to_list():
                    payload["bed"] = self.printer.bed_temperature.to_list()

        for i, tool in enumerate(self.printer.tool_temperatures):
            if i >= len(self.printer.server_tool_temperatures):
                payload[f"tool{i}"] = self.printer.tool_temperatures[i].to_list()
                continue

            if tool.to_list() != self.printer.server_tool_temperatures[i].to_list():
                payload[f"tool{i}"] = self.printer.tool_temperatures[i].to_list()

        self.printer.server_bed_temperature = copy.deepcopy(self.printer.bed_temperature)
        self.printer.server_tool_temperatures = copy.deepcopy(self.printer.tool_temperatures)

        if payload == {}:
            self.intervals.temperatures_updating = False
            return;

        self.__logger.debug(f"Sending temperatures: {payload}")
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
                self.__logger.error("invalid event")
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
     
    # ---------- events ---------- #

    def on_error(self, _: ErrorEvent) -> None:
        pass

    def on_new_token(self, _: NewTokenEvent) -> None:
        pass

    def on_connect(self, _: ConnectEvent) -> None:
        pass
    
    def on_setup_complete(self, _: SetupCompleteEvent) -> None:
        pass

    def on_interval_change(self, _: IntervalChangeEvent) -> None:
        pass

    def on_pong(self, _: PongEvent) -> None:
        pass

    def on_stream_received(self, _: StreamReceivedEvent) -> None:
        pass

    def on_printer_settings(self, _: PrinterSettingsEvent) -> None:
        pass

    def on_pause(self, _: PauseEvent) -> None:
        pass

    def on_resume(self, _: ResumeEvent) -> None:
        pass

    def on_cancel(self, _: CancelEvent) -> None:
        pass

    def on_terminal(self, _: TerminalEvent) -> None:
        pass

    def on_gcode(self, _: GcodeEvent) -> None:
        pass

    def on_webcam_test(self, _: WebcamTestEvent) -> None:
        pass

    def on_webcam_snapshot(self, _: WebcamSnapshotEvent) -> None:
        pass

    def on_file(self, _: FileEvent) -> None:
        pass

    def on_start_print(self, _: StartPrintEvent) -> None:
        pass

    def on_connect_printer(self, _: ConnectPrinterEvent) -> None:
        pass

    def on_disconnect_printer(self, _: DisconnectPrinterEvent) -> None:
        pass

    def on_system_restart(self, _: SystemRestartEvent) -> None:
        pass

    def on_system_shutdown(self, _: SystemShutdownEvent) -> None:
        pass

    def on_api_restart(self, _: ApiRestartEvent) -> None:
        pass

    def on_api_shutdown(self, _: ApiShutdownEvent) -> None:
        pass

    def on_update(self, _: UpdateEvent) -> None:
        pass

    def on_plugin_install(self, _: PluginInstallEvent) -> None:
        pass

    def on_plugin_uninstall(self, _: PluginUninstallEvent) -> None:
        pass

    def on_webcam_settings(self, _: WebcamSettingsEvent) -> None:
        pass

    def on_stream_on(self, _: StreamOnEvent) -> None:
        pass

    def on_stream_off(self, _: StreamOffEvent) -> None:
        pass

    def on_set_printer_profile(self, _: SetPrinterProfileEvent) -> None:
        pass

    def on_get_gcode_script_backups(self, _: GetGcodeScriptBackupsEvent) -> None:
        pass

    def on_has_gcode_changes(self, _: HasGcodeChangesEvent) -> None:
        pass

    def on_psu_control(self, _: PsuControlEvent) -> None:
        pass

    def on_disable_websocket(self, _: DisableWebsocketEvent) -> None:
        pass

    # ---------- event handlers ---------- #
    
    def handle_error_event(self, event: ErrorEvent) -> None:
        self.__logger.error(f"Error: {event.error}")

        self.intervals.reconnect = 30.0
        self.connection.reconnect_token = None

        self.on_error(event)
            
    def handle_new_token_event(self, event: NewTokenEvent) -> None:
        self.__logger.info(f"Received new token: {event.token} short id: {event.short_id}")

        self.connection.id = event.short_id
        self.connection.token = event.token

        if event.no_exist:
            self.printer.is_set_up = False

        self.on_new_token(event)
 
    def handle_connect_event(self, event: ConnectEvent) -> None:
        self.__logger.info(f"Connected to server")

        self.intervals.update(event.intervals)
        self.printer.connected = True
        self.printer.name = event.name
        self.connection.reconnect_token = event.reconnect_token

        self.on_connect(event)
    
    def handle_setup_complete_event(self, event: SetupCompleteEvent) -> None:
        self.__logger.info(f"Setup complete")

        self.connection.id = event.printer_id
        self.printer.is_set_up = True

        self.on_setup_complete(event)
    
    def handle_interval_change_event(self, event: IntervalChangeEvent) -> None:
        self.__logger.info(f"Interval change")

        self.intervals.update(event.intervals)
        self.on_interval_change(event)
    
    def handle_pong_event(self, event: PongEvent) -> None:
        self.__logger.info(f"Pong")

        self.on_pong(event)
    
    def handle_stream_received_event(self, event: StreamReceivedEvent) -> None:
        self.__logger.info(f"Stream received")

        self.on_stream_received(event)
    
    def handle_printer_settings_event(self, event: PrinterSettingsEvent) -> None:
        self.__logger.info(f"Printer settings")

        self.on_printer_settings(event)
    
    def handle_pause_event(self, event: PauseEvent) -> None:
        self.__logger.info(f"Pause")

        self.on_pause(event)
    
    def handle_resume_event(self, event: ResumeEvent) -> None:
        self.__logger.info(f"Resume")

        self.on_resume(event)
    
    def handle_cancel_event(self, event: CancelEvent) -> None:
        self.__logger.info(f"Cancel")

        self.on_cancel(event)
    
    def handle_terminal_event(self, event: TerminalEvent) -> None:
        self.__logger.info(f"Terminal")

        self.on_terminal(event)
    
    def handle_gcode_event(self, event: GcodeEvent) -> None:
        self.__logger.info(f"Gcode")

        self.on_gcode(event)
    
    def handle_webcam_test_event(self, event: WebcamTestEvent) -> None:
        self.__logger.info(f"Webcam test")

        self.on_webcam_test(event)
    
    def handle_webcam_snapshot_event(self, event: WebcamSnapshotEvent) -> None:
        self.__logger.info(f"Webcam snapshot")

        self.on_webcam_snapshot(event)
    
    def handle_file_event(self, event: FileEvent) -> None:
        self.__logger.info(f"File")

        self.on_file(event)
    
    def handle_start_print_event(self, event: StartPrintEvent) -> None:
        self.__logger.info(f"Start print")

        self.on_start_print(event)
    
    def handle_connect_printer_event(self, event: ConnectPrinterEvent) -> None:
        self.__logger.info(f"Connect printer")

        self.on_connect_printer(event)
    
    def handle_disconnect_printer_event(self, event: DisconnectPrinterEvent) -> None:
        self.__logger.info(f"Disconnect printer")

        self.on_disconnect_printer(event)
    
    def handle_system_restart_event(self, event: SystemRestartEvent) -> None:
        self.__logger.info(f"System restart")

        self.on_system_restart(event)
    
    def handle_system_shutdown_event(self, event: SystemShutdownEvent) -> None:
        self.__logger.info(f"System shutdown")

        self.on_system_shutdown(event)
    
    def handle_api_restart_event(self, event: ApiRestartEvent) -> None:
        self.__logger.info(f"API restart")

        self.on_api_restart(event)
    
    def handle_api_shutdown_event(self, event: ApiShutdownEvent) -> None:
        self.__logger.info(f"API shutdown")

        self.on_api_shutdown(event)
    
    def handle_update_event(self, event: UpdateEvent) -> None:
        self.__logger.info(f"Update")

        self.on_update(event)
    
    def handle_plugin_install_event(self, event: PluginInstallEvent) -> None:
        self.__logger.info(f"Plugin install")

        self.on_plugin_install(event)
    
    def handle_plugin_uninstall_event(self, event: PluginUninstallEvent) -> None:
        self.__logger.info(f"Plugin uninstall")

        self.on_plugin_uninstall(event)
    
    def handle_webcam_settings_event(self, event: WebcamSettingsEvent) -> None:
        self.__logger.info(f"Webcam settings")

        self.on_webcam_settings(event)
    
    def handle_stream_on_event(self, event: StreamOnEvent) -> None:
        self.__logger.info(f"Stream on")

        self.on_stream_on(event)
    
    def handle_stream_off_event(self, event: StreamOffEvent) -> None:
        self.__logger.info(f"Stream off")

        self.on_stream_off(event)
    
    def handle_set_printer_profile_event(self, event: SetPrinterProfileEvent) -> None:
        self.__logger.info(f"Set printer profile")

        self.on_set_printer_profile(event)
    
    def handle_get_gcode_script_backups_event(self, event: GetGcodeScriptBackupsEvent) -> None:
        self.__logger.info(f"Get gcode script backups")

        self.on_get_gcode_script_backups(event)
    
    def handle_has_gcode_changes_event(self, event: HasGcodeChangesEvent) -> None:
        self.__logger.info(f"Has gcode changes")

        self.on_has_gcode_changes(event)
    
    def handle_psu_control_event(self, event: PsuControlEvent) -> None:
        self.__logger.info(f"PSU control")

        self.on_psu_control(event)
    
    def handle_disable_websocket_event(self, event: DisableWebsocketEvent) -> None:
        self.__logger.info(f"Disable websocket")

        self.on_disable_websocket(event)

