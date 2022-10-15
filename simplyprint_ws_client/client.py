import asyncio
import logging
import json
import copy
import time
import sentry_sdk
import platform
import netifaces
import socket
import os
import psutil
import subprocess
import re
import functools
import base64

from concurrent.futures import Future
from .ambient import AmbientCheck
from .printer_state import Printer, PrinterStatus, Temperature
from .connection import Connection
from .event import *
from .timer import Intervals
from .async_loop import AsyncLoop
from .config import Config
from .file import FileHandler, requests

SNAPSHOT_ENDPOINT = "https://apirewrite.simplyprint.io/jobs/ReceiveSnapshot"
AI_ENDPOINT = "https://ai.simplyprint.io/api/v2/infer"
VERSION = "0.0.1"

from logging import Logger
from typing import List, Optional

class ClientInfo:
    ui: Optional[str] = None
    ui_version: Optional[str] = None
    api: Optional[str] = None
    api_version: Optional[str] = None
    client: Optional[str] = None
    client_version: Optional[str] = None
    sp_version: Optional[str] = "4.0.0"
    sentry_dsn: Optional[str] = None
    development: bool = False

    def python_version(self) -> str:
        return platform.python_version() 

    def __get_cpu_model_linux(self) -> Optional[str]:
        info_path = "/proc/cpuinfo"

        try:
            with open(info_path, "r") as f:
                data = f.read()

            cpu_items = [
                item.strip() for item in data.split("\n\n") if item.strip()
            ]

            match = re.search(r"Model\s+:\s+(.+)", cpu_items[-1])
            if not match is None:
                return match.group(1)

            for item in cpu_items:
                match = re.search(r"model name\s+:\s+(.+)", item)

                if not match is None:
                    return match.group(1).strip()
        except Exception:
            pass

    def __get_cpu_model_windows(self) -> Optional[str]:
        try:
            name = subprocess.check_output(["wmic", "cpu", "get", "name"]).decode("utf-8").strip()

            if name.startswith("Name"):
                name = name[4:].strip()
            
            return name
        except Exception:
            return None

    def machine(self) -> str:
        if self.os() == "Linux":
            model = self.__get_cpu_model_linux()

            if not model is None:
                return model

        if self.os() == "Windows":
            model = self.__get_cpu_model_windows()

            if not model is None:
                return model
    
        return platform.machine()

    def os(self) -> str:
        return platform.system()

    def is_ethernet(self) -> bool:
        try:
            return netifaces.gateways()["default"][netifaces.AF_INET][1].startswith("eth")
        except Exception:
            return False

    def __ssid_linux(self) -> Optional[str]:
        try:
            return subprocess.check_output(["iwgetid", "-r"]).decode("utf-8").strip()
        except Exception:
            return None

    def __ssid_windows(self) -> Optional[str]:
        try:
            output = subprocess.check_output(["netsh", "wlan", "show", "interfaces"]).decode("utf-8").strip()

            for line in output.split("\n"):
                line = line.strip()

                if line.startswith("SSID"):
                    return line[4:].strip()[1:].strip()

            return None
        except Exception:
            return None

    def ssid(self) -> Optional[str]:
        if self.os() == "Linux":
            return self.__ssid_linux()

        if self.os() == "Windows":
            return self.__ssid_windows()

        return None

    def hostname(self) -> str:
        return socket.gethostname()

    def local_ip(self) -> Optional[str]:
        try:
            interface = netifaces.gateways()["default"][netifaces.AF_INET][1]

            return netifaces.ifaddresses(interface)[netifaces.AF_INET][0]["addr"]
        except Exception:
            return None

    def core_count(self) -> Optional[int]:
        return os.cpu_count()

    def total_memory(self) -> int:
        return psutil.virtual_memory().total
        

class Client: 
    __logger: Logger = logging.getLogger("simplyprint.client")

    config: Config = Config()
    info: ClientInfo = ClientInfo()

    local_path: Optional[str] = None
    display_messages_enabled: bool = True

    use_opencv: bool = False

    connection: Connection = Connection(logging.getLogger("simplyprint.client.connection"))
    printer: Printer = Printer()
    intervals: Intervals = Intervals() 
    ping_queue: List[float] = []

    snapshot_endpoint: str = SNAPSHOT_ENDPOINT

    loop: AsyncLoop = AsyncLoop()
    process_task: Optional[Future] = None  

    file_handler: Optional[FileHandler] = None
    __been_offline: bool = False
    __selected_file: Optional[str] = None
    __webcam_connected: bool = False
    __ai_scores: List[float] = []
    __display_message_loop: Optional[Future] = None
    __ambient_check: Optional[AmbientCheck] = None

    # ---------- control ---------- # 
    
    # starts the client
    # this initializes the connection and starts the event loop
    # this should be called after the client has been configured
    def start(self) -> None:
        # start sentry
        self.__start_sentry()

        # set up FileHandler
        if self.local_path is None:
            raise Exception("local_path not set for Client")

        self.file_handler = FileHandler(self, self.local_path)

        # start AsyncLoop
        self.loop.start() 

        self.__initialize_webcam()
        self.__initialize_connection()

        ambient_check = AmbientCheck(self.__set_ambient)
        self.__ambient_check = ambient_check
        self.printer.status = PrinterStatus.OPERATIONAL
        self.send_status()

        self.process_task = self.loop.spawn(self.process_events())
        self.loop.spawn(self.send_cpu_loop())
        self.loop.spawn(self.send_ping_loop())
        self.loop.spawn(self.__ambient_check.run_loop(self.printer))

    def __initialize_webcam(self) -> None:
        if self.use_opencv:
            import cv2

            self.__logger.info("using OpenCV for webcam")
            self.__webcam = cv2.VideoCapture(-1) 
            self.__webcam_connected = self.__webcam.isOpened()

    def __initialize_connection(self) -> None:
        self.send_firmware()
        self.send_machine_data()
        self.send_webcam_connected() 

    def __del__(self):
        self.stop()
    
    # sets status to OFFLINE, stops the AsyncLoop
    def stop(self) -> None:
        self.status = PrinterStatus.OFFLINE
        self.loop.stop() 

    def __start_sentry(self):
        if self.info.sentry_dsn is None:
            return

        self.__logger.debug("Initializing Sentry")

        if self.info.development:
            environment = "development"
        else:
            environment = "production"

        try:
            sentry_sdk.init(
                dsn=self.info.sentry_dsn,
                traces_sample_rate=0.05,
                release=f"{self.info.client}@{self.info.client_version}",
                environment=environment,
            )
            sentry_sdk.set_tag("lib_version", VERSION)
            if self.config.id != "0":
                sentry_sdk.set_user({"id": self.config.id})
        except Exception:
            self.__logger.debug("Failed to connect to sentry")

    # ---------- info ---------- #

    def __get_firmware(self) -> Dict[str, Any]:
        return { "fw": self.printer.firmware.dict() }

    # sends firmware to server, this is called at start
    def send_firmware(self) -> None:
        firmware = self.__get_firmware()
        self.__logger.debug(f"Sending firmware: {firmware}")
        self.send(PrinterEvent.FIRMWARE, firmware)

    def __get_cpu(self) -> Dict[str, Any]:
        temperature: Optional[float] = None
        temperatures = psutil.sensors_temperatures()

        if "coretemp" in temperatures:
            temperature = temperatures["coretemp"][0].current
        if "cpu-thermal" in temperatures:
            temperature = temperatures["cpu-thermal"][0].current
        if "cpu_thermal" in temperatures:
            temperature = temperatures["cpu_thermal"][0].current
        if "soc_thermal" in temperatures:
            temperature = temperatures["soc_thermal"][0].current

        if temperature is None:
            temperature = 0
    
        return {
            "usage": round(psutil.cpu_percent()),
            "temp": round(temperature),
            "memory": round(psutil.virtual_memory().percent),
            "flags": 0,
        }

    # sends cpu to server, this is called at a fixed interval by send_cpu_loop
    def send_cpu(self) -> None:
        cpu = self.__get_cpu()
        self.__logger.debug(f"Sending CPU info: {cpu}")
        self.send(PrinterEvent.CPU, cpu)

    def __get_machine_data(self) -> Dict[str, Any]:
        return {
            "ui": self.info.ui,
            "ui_version": self.info.ui_version,
            "api": self.info.api,
            "api_version": self.info.api_version,
            "sp_version": self.info.sp_version,
            "python_version": self.info.python_version(),
            "machine": self.info.machine(),
            "os": self.info.os(),
            "is_ethernet": self.info.is_ethernet(),
            "ssid": self.info.ssid(),
            "hostname": self.info.hostname(),
            "local_ip": self.info.local_ip(),
            "core_count": self.info.core_count(),
            "total_memory": self.info.total_memory(),
        }

    # sends machine_data to server, this is called at start
    def send_machine_data(self):
        machine_data = self.__get_machine_data()
        self.__logger.debug(f"Sending machine data: {machine_data}")
        self.send(PrinterEvent.MACHINE_DATA, machine_data)

    # ---------- client events ---------- #  

    @property
    def id(self) -> Optional[str]:
        return self.config.id

    @id.setter
    def id(self, id: str) -> None:
        self.config.id = id

    @property
    def token(self) -> Optional[str]:
        return self.config.token
    
    @token.setter
    def token(self, token: str) -> None:
        self.config.token = token 

    @property
    def status(self) -> PrinterStatus:
        return self.printer.status
    
    @status.setter
    def status(self, status: PrinterStatus) -> None:
        if self.printer.status == status:
            return

        self.__logger.debug(f"Status changed from {self.printer.status} to {status}")  

        self.printer.status = status
        
        self.update_display_message()

    @property
    def selected_file(self) -> Optional[str]:
        return self.__selected_file

    @property
    def webcam_connected(self) -> bool:
        return self.__webcam_connected

    @webcam_connected.setter
    def webcam_connected(self, connected: bool) -> None:
        if self.__webcam_connected == connected:
            return

        self.__webcam_connected = connected
        self.send_webcam_connected()

    @property
    def ambient_temperature(self) -> Optional[float]:
        return self.printer.ambient_temperature

    @ambient_temperature.setter
    def ambient_temperature(self, temperature: float) -> None:
        self.printer.ambient_temperature = temperature

        if round(self.printer.ambient_temperature) != round(temperature):
            self.send(PrinterEvent.AMBIENT, 
                { "new": round(temperature) },
            )

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
    
    # waits for the appropriate interval to pass before sending temperatures
    async def send_temperatures(self) -> None:
        if self.printer.is_heating():
            await self.intervals.sleep_until_target_temperatures()
        else:
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

    # internal setter for ambient temperature
    # used as callback for AmbientCheck
    def __set_ambient(self, temperature: int) -> None:
        self.ambient_temperature = float(temperature)

        self.send(
            PrinterEvent.AMBIENT, 
            { "new": temperature },
        )

    # send webcam connected status
    def send_webcam_connected(self):
        self.__logger.debug(f"Sending webcam connected: {self.__webcam_connected}")
        self.send(PrinterEvent.WEBCAM_STATUS, {
            "connected": self.webcam_connected,
        })

    def send_status(self):
        self.send(PrinterEvent.STATUS, {
            "new": self.printer.status.value,
        })
 
    # starts a print, this is usually called internally
    def start_print(self): 
        self.send_job_update({"started": True})

        self.status = PrinterStatus.PRINTING
        self.loop.spawn(self.handle_start_print_event(StartPrintEvent()))

    # call this when the print is done
    def print_done(self):
        self.send_job_update({"finished": True})

        self.status = PrinterStatus.OPERATIONAL

    # sends a job update to the server
    def send_job_update(self, job_info: Dict[str, Any]):
        self.send(PrinterEvent.JOB_INFO, job_info)

    # call this when the print is starts canceling
    def cancel_print(self, error: str) -> None:
        self.send_job_error(error)
        self.status = PrinterStatus.CANCELLING
        self.loop.spawn(self.handle_cancel_event(CancelEvent()))

    # call this when the print is done canceling
    def print_cancelled(self) -> None:
        self.status = PrinterStatus.OPERATIONAL

    # a loop that sends cpu updates
    async def send_cpu_loop(self):
        while True:
            await self.intervals.sleep_until_cpu()
            self.send_cpu()

    def get_base64_url(self, url: str) -> Optional[str]:
        headers = { "Accept": "image/jpeg" }
        try:
            response = requests.get(url, headers=headers, verify=False, timeout=2)
        except Exception:
            return None

        return base64.b64encode(response.content).decode()

    def set_display_message(self, message: str, short_branding: bool = False, spawn_loop: bool = True) -> None:
        if not self.display_messages_enabled:
            return

        if self.printer.current_display_message == message:
            return
     
        self.printer.current_display_message = message

        event = DisplayMessageEvent(message, short_branding)
        self.loop.spawn(self.handle_display_message_event(event))

        if not spawn_loop:
            return

        if not self.__display_message_loop is None:
            self.__display_message_loop.cancel()

        self.__display_message_loop = self.loop.spawn(self.display_message_loop())

    def update_display_message(self, spawn_loop: bool = True) -> None:
        if not self.connection.is_connected() and not self.is_online():
            self.set_display_message("No internet", spawn_loop=spawn_loop)
            return

        if self.status == PrinterStatus.OPERATIONAL:
            self.set_display_message("Ready", spawn_loop=spawn_loop)
            return

        if self.status == PrinterStatus.PRINTING:
            self.set_display_message(f"Printing '{self.selected_file}'", spawn_loop=spawn_loop)
            return

        if self.status == PrinterStatus.PAUSING:
            self.set_display_message("Pausing", spawn_loop=spawn_loop)
            return

        if self.status == PrinterStatus.PAUSED:
            self.set_display_message("Paused", spawn_loop=spawn_loop)
            return

        if self.status == PrinterStatus.CANCELLING:
            self.set_display_message("Cancelling", spawn_loop=spawn_loop)
            return

    async def display_message_loop(self) -> None:
        first = True
        while True:
            if first:
                await asyncio.sleep(20.0)
            else:
                await asyncio.sleep(60.0)

            if not self.printer.current_display_message is None:
                self.update_display_message()

            first = False

    # ---------- io ---------- #

    def send_job_error(self, error: str) -> None:
        self.send(
            PrinterEvent.JOB_INFO, 
            { "error": error },
        )
 
    # sends a PrinterEvent to the server
    def send(self, event: PrinterEvent, data: Any) -> Future:
        return self.loop.spawn(self.send_async(event, data))
 
    async def send_async(self, event: PrinterEvent, data: Any) -> None:
        if data is None:
            message = json.dumps({
                "type": event.value,
            })
        else:
            message = json.dumps({
                "type": event.value,
                "data": data,
            })

        await self.send_message_async(message)
    
    # spawns a new task to send the message
    def send_message(self, message: str) -> None:
        self.loop.spawn(self.send_message_async(message))

    def is_online(self) -> bool:
        try:
            requests.get("https://www.google.com", timeout=2)
            return True
        except Exception:
            self.__been_offline = True
            return False
    
    # connect to the server, if it fails, will try again every reconnect interval FOR EVER
    # TODO: this is a bit of a mess, clean it up
    async def connect(self):
        if not self.connection.is_connected() and not self.intervals.reconnect_updating and self.is_online():
            self.set_display_message("Connecting...")

        while not self.connection.is_connected():
            if self.intervals.reconnect_updating:
                # if we're already connecting, we don't need this read to trigger another connection
                # but we still need to wait until we have connected.
                # but i honestly can't figure out how to do it better than this
                # TODO: fix pls
                await asyncio.sleep(1.0)
                continue


            self.intervals.reconnect_updating = True

            if not self.connection.reconnect_token is None:
                await self.intervals.sleep_until_reconnect()
            else:
                await asyncio.sleep(1.0)

            await self.connection.connect(self.config.id, self.config.token)

            if self.connection.is_connected():
                if self.__been_offline:
                    self.__been_offline = False
                    self.set_display_message("Back online!")
                else:
                    self.set_display_message("Connected")
            elif not self.is_online():
                self.set_display_message("No internet")
            else:
                self.set_display_message("Can't reach SP")

            self.intervals.reconnect_updating = False

    async def send_message_async(self, message: str) -> None:
        await self.connect()
        await self.connection.send_message(message)

    # posts a snapshot to the server at self.snapshot_endpoint
    async def post_snapshot(self, id: str, data: str) -> None:
        headers = { "User-Agent": "Mozilla/5.0" }
        await self.loop.aioloop.run_in_executor(
            None,
            functools.partial(
                requests.post, 
                self.snapshot_endpoint, 
                data={
                    "id": id,
                    "data": data,
                }, 
                headers=headers, 
                timeout=45.0,
            )
        )

    # sends a snapshot to the server though the websocket
    async def stream_snapshot(self, data: str) -> None:
        self.__logger.debug("Streaming snapshot, sending")
        await self.send_async(PrinterEvent.STREAM, {"base": data})

    async def __make_ai_request(self, endpoint: str, data: str, headers: Dict[str, str], timeout: float = 10.0):
        return await self.loop.aioloop.run_in_executor(
            None,
            functools.partial(
                requests.post, endpoint, data=data, headers=headers,
                timeout=timeout
            )
        )

    async def __handle_ai_snapshot(self) -> bool:
        snapshot = await self.on_webcam_snapshot(WebcamSnapshotEvent({}))
        if snapshot is None:
            self.__logger.error("Webcam snapshot was None")
            return False

        headers = { "User-Agent": "Mozilla/5.0" }
        data = {
            "api_key": self.config.token,     
            "image_array": snapshot,
            "interval": self.intervals.ai,
            "printer_id": self.config.id,
            "settings": {
                "buffer_percent": 80.0,
                "confidence": 60.0,
                "buffer_length": 16.0,
            },
            "scores": self.__ai_scores,
        }
        json_data = json.dumps(data)

        try:
            response = await self.__make_ai_request(AI_ENDPOINT, json_data, headers)
        except Exception:
            return False

        response_json = response.json()
        self.__ai_scores = response_json.get("scores", self.__ai_scores)
        self.send(
            PrinterEvent.AI_RESPONSE, 
            {
                "ai": response_json.get("s1", [0.0, 0.0, 0.0]),
            }
        )

        return True

    def __should_run_ai(self) -> bool:
        return self.intervals.ai > 0.0 and self.webcam_connected and self.status == PrinterStatus.PRINTING

    async def ai_loop(self):
        failed_ai_attempts = 120.0
        delay = self.intervals.ai

        while self.__should_run_ai():
            await asyncio.sleep(delay)

            if await self.__handle_ai_snapshot():
                failed_ai_attempts = 0.0
                delay = self.intervals.ai
            else:
                failed_ai_attempts += 1.0
                delay = self.intervals.ai + (failed_ai_attempts * 5.0) if failed_ai_attempts < 10.0 else 120.0

    # ---------- server events ---------- #

    # a loop that sends pings to the server 
    async def send_ping_loop(self) -> None:
        while True:
            await self.intervals.sleep_until_ping()
            await self.send_async(PrinterEvent.PING, None)
            self.ping_queue.append(time.time() * 1000.0)
    
    # receives events in a loop and spawns the appropriate handlers
    async def process_events(self):
        while True:
            await self.connect()

            event = await self.connection.read_event()

            if event is None:
                self.__logger.error("invalid event")
                continue

            self.loop.spawn(self.handle_event(event))
    
    # handles a single event
    async def handle_event(self, event: Event) -> None:
        await self.on_event(event)

        if isinstance(event, NewTokenEvent):
            await self.handle_new_token_event(event)
        elif isinstance(event, ConnectEvent):
            await self.handle_connect_event(event)
        elif isinstance(event, SetupCompleteEvent):
            await self.handle_setup_complete_event(event)
        elif isinstance(event, IntervalChangeEvent):
            await self.handle_interval_change_event(event)
        elif isinstance(event, PongEvent):
            await self.handle_pong_event(event)
        elif isinstance(event, StreamReceivedEvent):
            await self.handle_stream_received_event(event)
        elif isinstance(event, PrinterSettingsEvent):
            await self.handle_printer_settings_event(event)
        elif isinstance(event, PauseEvent):
            await self.handle_pause_event(event)
        elif isinstance(event, ResumeEvent):
            await self.handle_resume_event(event)
        elif isinstance(event, CancelEvent):
            await self.handle_cancel_event(event)
        elif isinstance(event, TerminalEvent):
            await self.handle_terminal_event(event)
        elif isinstance(event, GcodeEvent):
            await self.handle_gcode_event(event)
        elif isinstance(event, WebcamTestEvent):
            await self.handle_webcam_test_event(event)
        elif isinstance(event, WebcamSnapshotEvent):
            await self.handle_webcam_snapshot_event(event)
        elif isinstance(event, FileEvent):
            await self.handle_file_event(event)
        elif isinstance(event, StartPrintEvent):
            await self.handle_start_print_event(event)
        elif isinstance(event, ConnectPrinterEvent):
            await self.handle_connect_printer_event(event)
        elif isinstance(event, DisconnectPrinterEvent):
            await self.handle_disconnect_printer_event(event)
        elif isinstance(event, SystemRestartEvent):
            await self.handle_system_restart_event(event)
        elif isinstance(event, SystemShutdownEvent):
            await self.handle_system_shutdown_event(event)
        elif isinstance(event, ApiRestartEvent):
            await self.handle_api_restart_event(event)
        elif isinstance(event, ApiShutdownEvent):
            await self.handle_api_shutdown_event(event)
        elif isinstance(event, UpdateEvent):
            await self.handle_update_event(event)
        elif isinstance(event, PluginInstallEvent):
            await self.handle_plugin_install_event(event)
        elif isinstance(event, PluginUninstallEvent):
            await self.handle_plugin_uninstall_event(event)
        elif isinstance(event, WebcamSettingsEvent):
            await self.handle_webcam_settings_event(event)
        elif isinstance(event, StreamOnEvent):
            await self.handle_stream_on_event(event)
        elif isinstance(event, StreamOffEvent):
            await self.handle_stream_off_event(event)
        elif isinstance(event, SetPrinterProfileEvent):
            await self.handle_set_printer_profile_event(event)
        elif isinstance(event, GetGcodeScriptBackupsEvent):
            await self.handle_get_gcode_script_backups_event(event)
        elif isinstance(event, HasGcodeChangesEvent):
            await self.handle_has_gcode_changes_event(event)
        elif isinstance(event, PsuControlEvent):
            await self.handle_psu_control_event(event)
        elif isinstance(event, DisableWebsocketEvent):
            await self.handle_disable_websocket_event(event)
     
    # ---------- events ---------- #

    async def on_event(self, _: Event) -> None:
        pass

    async def on_error(self, _: ErrorEvent) -> None:
        pass

    async def on_new_token(self, _: NewTokenEvent) -> None:
        pass

    async def on_connect(self, _: ConnectEvent) -> None:
        pass
    
    async def on_setup_complete(self, _: SetupCompleteEvent) -> None:
        pass

    async def on_interval_change(self, _: IntervalChangeEvent) -> None:
        pass

    async def on_pong(self, _: PongEvent) -> None:
        pass

    async def on_stream_received(self, _: StreamReceivedEvent) -> None:
        pass

    async def on_printer_settings(self, _: PrinterSettingsEvent) -> None:
        pass

    async def on_pause(self, _: PauseEvent) -> None:
        pass

    async def on_resume(self, _: ResumeEvent) -> None:
        pass

    async def on_cancel(self, _: CancelEvent) -> None:
        self.print_cancelled()

    async def on_terminal(self, _: TerminalEvent) -> None:
        pass

    async def on_display_message(self, event: DisplayMessageEvent) -> None:
        message = event.message

        if self.printer.settings.display.branding:
            if event.short_branding or len(message) > 7:
                message = f"[SP] {message}"
            else:
                message = f"[SimplyPrint] {message}"

        gcode_event = GcodeEvent();
        gcode_event.list = [f"M117 {event.message}"]

        await self.handle_gcode_event(gcode_event)

    async def on_gcode(self, _: GcodeEvent) -> None:
        pass

    async def on_webcam_test(self, _: WebcamTestEvent) -> None:
        self.__initialize_webcam()

    async def on_webcam_snapshot(self, _: WebcamSnapshotEvent) -> Optional[str]:
        if not self.use_opencv:
            self.__logger.warn("Webcam snapshot requested but OpenCV is not used and event is not overridden")

            return None

        if not hasattr(self, "_Client__webcam"):
            return None

        import cv2

        MAX_WIDTH = 1280
        MAX_HEIGHT = 720

        _, frame = self.__webcam.read() 
        aspect = frame.shape[1] / frame.shape[0]

        if frame.shape[0] > MAX_HEIGHT:
            frame = cv2.resize(frame, (int(MAX_HEIGHT * aspect), MAX_HEIGHT))

        if frame.shape[1] > MAX_HEIGHT * aspect:
            frame = cv2.resize(frame, (MAX_WIDTH, int(MAX_HEIGHT / aspect)))

        _, buffer = cv2.imencode(".jpg", frame)
        img_bytes = buffer.tobytes();
        data = base64.b64encode(img_bytes).decode()

        return data

    async def on_file(self, _: FileEvent) -> None:
        pass

    async def on_start_print(self, _: StartPrintEvent) -> None:
        pass

    async def on_connect_printer(self, _: ConnectPrinterEvent) -> None:
        pass

    async def on_disconnect_printer(self, _: DisconnectPrinterEvent) -> None:
        pass

    async def on_system_restart(self, _: SystemRestartEvent) -> None:
        if platform.system() == "Linux":
            os.system("reboot")
        elif platform.system() == "Windows":
            os.system("shutdown /r")

    async def on_system_shutdown(self, _: SystemShutdownEvent) -> None:
        if platform.system() == "Linux":
            os.system("shutdown now")
        elif platform.system() == "Windows":
            os.system("shutdown /s")

    async def on_api_restart(self, _: ApiRestartEvent) -> None:
        pass

    async def on_api_shutdown(self, _: ApiShutdownEvent) -> None:
        pass

    async def on_update(self, _: UpdateEvent) -> None:
        pass

    async def on_plugin_install(self, _: PluginInstallEvent) -> None:
        pass

    async def on_plugin_uninstall(self, _: PluginUninstallEvent) -> None:
        pass

    async def on_webcam_settings(self, _: WebcamSettingsEvent) -> None:
        pass

    async def on_stream_on(self, _: StreamOnEvent) -> None:
        pass

    async def on_stream_off(self, _: StreamOffEvent) -> None:
        pass

    async def on_set_printer_profile(self, _: SetPrinterProfileEvent) -> None:
        pass

    async def on_get_gcode_script_backups(self, _: GetGcodeScriptBackupsEvent) -> None:
        pass

    async def on_has_gcode_changes(self, _: HasGcodeChangesEvent) -> None:
        pass

    async def on_psu_control(self, _: PsuControlEvent) -> None:
        pass

    async def on_disable_websocket(self, _: DisableWebsocketEvent) -> None:
        pass

    # ---------- event handlers ---------- #
    
    async def handle_error_event(self, event: ErrorEvent) -> None:
        self.__logger.error(f"Error: {event.error}")

        self.intervals.reconnect = 30.0
        self.connection.reconnect_token = None

        await self.on_error(event)
            
    async def handle_new_token_event(self, event: NewTokenEvent) -> None:
        self.__logger.info(f"Received new token: {event.token} short id: {event.short_id}")

        self.config.token = event.token

        self.config.save()

        self.set_display_message(f"{event.short_id}")

        if event.no_exist:
            self.printer.is_set_up = False

        await self.on_new_token(event)
 
    async def handle_connect_event(self, event: ConnectEvent) -> None:
        self.__logger.info(f"Connected to server")

        self.intervals.update(event.intervals)
        self.printer.connected = True
        self.printer.name = event.name
        self.connection.reconnect_token = event.reconnect_token

        if event.in_set_up:
            self.printer.is_set_up = False

        await self.on_connect(event)
    
    async def handle_setup_complete_event(self, event: SetupCompleteEvent) -> None:
        self.__logger.info(f"Setup complete")

        self.config.id = event.printer_id
        self.printer.is_set_up = True

        sentry_sdk.set_user({"id": event.printer_id})

        self.config.save()

        self.set_display_message("Setup complete")

        await self.on_setup_complete(event)
    
    async def handle_interval_change_event(self, event: IntervalChangeEvent) -> None:
        self.__logger.info(f"Interval change")

        self.intervals.update(event.intervals)
        await self.on_interval_change(event)
    
    async def handle_pong_event(self, event: PongEvent) -> None:
        self.__logger.info(f"Pong")

        if len(self.ping_queue) > 0:
            ping = self.ping_queue.pop(0)
            latency = time.time() * 1000.0 - ping
            self.send(PrinterEvent.LATENCY, {"ms": round(latency)})
        else:
            self.__logger.error(f"Received pong without ping")


        await self.on_pong(event)
    
    async def handle_stream_received_event(self, event: StreamReceivedEvent) -> None:
        self.__logger.info(f"Stream received")

        await self.on_stream_received(event)
    
    async def handle_printer_settings_event(self, event: PrinterSettingsEvent) -> None:
        self.__logger.info(f"Printer settings")

        await self.on_printer_settings(event)
    
    async def handle_pause_event(self, event: PauseEvent) -> None:
        self.__logger.info(f"Pause")

        await self.on_pause(event)
    
    async def handle_resume_event(self, event: ResumeEvent) -> None:
        self.__logger.info(f"Resume")

        await self.on_resume(event)
    
    async def handle_cancel_event(self, event: CancelEvent) -> None:
        self.__logger.info(f"Cancel Print")

        self.status = PrinterStatus.CANCELLING

        await self.on_cancel(event)
    
    async def handle_terminal_event(self, event: TerminalEvent) -> None:
        self.__logger.info(f"Terminal")

        await self.on_terminal(event)

    async def handle_display_message_event(self, event: DisplayMessageEvent) -> None:
        self.__logger.info(f"Display message")

        await self.on_display_message(event)
    
    async def handle_gcode_event(self, event: GcodeEvent) -> None:
        self.__logger.info(f"Gcode")

        await self.on_gcode(event)
    
    async def handle_webcam_test_event(self, event: WebcamTestEvent) -> None:
        self.__logger.info(f"Webcam test")

        self.send_webcam_connected()
        await self.on_webcam_test(event)
    
    async def handle_webcam_snapshot_event(self, event: WebcamSnapshotEvent) -> None:
        self.__logger.info(f"Webcam snapshot")

        if not event.timer is None:
            await asyncio.sleep(event.timer  / 1000.0)

        if not self.webcam_connected:
            return
        
        snapshot = await self.on_webcam_snapshot(event)

        if not snapshot is None:
            if not event.id is None:
                await self.post_snapshot(event.id, snapshot)
            else:
                await self.stream_snapshot(snapshot)
        else:
            self.__logger.error(f"Snapshot was requested but None was returned")
    
    async def handle_file_event(self, event: FileEvent) -> None:
        self.__logger.info(f"File")

        if self.file_handler is None:
            raise Exception("Client not started")

        if not event.url is None:
            self.__selected_file = self.file_handler.download(event.url)
            event.path = self.__selected_file
            self.set_display_message("Starting...")
        
        if not event.path is None:
            self.__selected_file = event.path

        if event.auto_start:
            self.start_print()

        await self.on_file(event)
    
    async def handle_start_print_event(self, event: StartPrintEvent) -> None:
        self.__logger.info(f"Start print")

        self.loop.spawn(self.ai_loop())
        await self.on_start_print(event)
    
    async def handle_connect_printer_event(self, event: ConnectPrinterEvent) -> None:
        self.__logger.info(f"Connect printer")

        await self.on_connect_printer(event)
    
    async def handle_disconnect_printer_event(self, event: DisconnectPrinterEvent) -> None:
        self.__logger.info(f"Disconnect printer")

        await self.on_disconnect_printer(event)
    
    async def handle_system_restart_event(self, event: SystemRestartEvent) -> None:
        self.__logger.info(f"System restart")

        await self.on_system_restart(event)
    
    async def handle_system_shutdown_event(self, event: SystemShutdownEvent) -> None:
        self.__logger.info(f"System shutdown")

        await self.on_system_shutdown(event)
    
    async def handle_api_restart_event(self, event: ApiRestartEvent) -> None:
        self.__logger.info(f"API restart")

        await self.on_api_restart(event)
    
    async def handle_api_shutdown_event(self, event: ApiShutdownEvent) -> None:
        self.__logger.info(f"API shutdown")

        await self.on_api_shutdown(event)
    
    async def handle_update_event(self, event: UpdateEvent) -> None:
        self.__logger.info(f"Update")

        await self.on_update(event)
    
    async def handle_plugin_install_event(self, event: PluginInstallEvent) -> None:
        self.__logger.info(f"Plugin install")

        await self.on_plugin_install(event)
    
    async def handle_plugin_uninstall_event(self, event: PluginUninstallEvent) -> None:
        self.__logger.info(f"Plugin uninstall")

        await self.on_plugin_uninstall(event)
    
    async def handle_webcam_settings_event(self, event: WebcamSettingsEvent) -> None:
        self.__logger.info(f"Webcam settings")

        await self.on_webcam_settings(event)
    
    async def handle_stream_on_event(self, event: StreamOnEvent) -> None:
        self.__logger.info(f"Stream on")

        await self.on_stream_on(event)
    
    async def handle_stream_off_event(self, event: StreamOffEvent) -> None:
        self.__logger.info(f"Stream off")

        await self.on_stream_off(event)
    
    async def handle_set_printer_profile_event(self, event: SetPrinterProfileEvent) -> None:
        self.__logger.info(f"Set printer profile")

        await self.on_set_printer_profile(event)
    
    async def handle_get_gcode_script_backups_event(self, event: GetGcodeScriptBackupsEvent) -> None:
        self.__logger.info(f"Get gcode script backups")

        await self.on_get_gcode_script_backups(event)
    
    async def handle_has_gcode_changes_event(self, event: HasGcodeChangesEvent) -> None:
        self.__logger.info(f"Has gcode changes")

        await self.on_has_gcode_changes(event)
    
    async def handle_psu_control_event(self, event: PsuControlEvent) -> None:
        self.__logger.info(f"PSU control")

        await self.on_psu_control(event)
    
    async def handle_disable_websocket_event(self, event: DisableWebsocketEvent) -> None:
        self.__logger.info(f"Disable websocket")

        await self.on_disable_websocket(event)

