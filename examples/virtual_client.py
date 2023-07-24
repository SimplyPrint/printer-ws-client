import math
import asyncio

from simplyprint_ws_client.helpers.file_download import FileDownload
from simplyprint_ws_client.helpers.temperature import Temperature
from simplyprint_ws_client.client import DefaultClient
from simplyprint_ws_client.config import Config

from simplyprint_ws_client.events import Events, Demands, ClientEvent

from simplyprint_ws_client.printer import PrinterStatus

def expt_smooth(target, actual, alpha, dt):
    return actual + (target - actual) * (1.0 - math.exp(-alpha * dt))

class VirtualSuperClient(DefaultClient):
    def __init__(self, config: Config):
        super().__init__(config)

        self.sentry.client = "VirtualSuperClient"
        self.sentry.client_version = "0.0.1"
        self.sentry.sentry_dsn = "https://a5aef1defa83433586dd0cf1c1fffe57@o1102514.ingest.sentry.io/6619552"
        self.sentry.development = True

        self.printer.info.api = "Virtual"
        self.printer.info.api_version = "0.1"
        self.printer.info.ui = "Virtual"
        self.printer.info.ui_version = "0.1"
        self.printer.info.sp_version = "4.1.0"

        self.printer.bed_temperature = Temperature(actual=20.0)
        self.printer.tool_temperatures = [
            Temperature(actual=20.0)
        ]

        self.printer.status = PrinterStatus.OPERATIONAL

        for k, v in self.physical_machine.get_info().items():
            self.printer.info.set_trait(k, v)

    @Events.ConnectEvent.on
    async def on_connect(self, event: Events.ConnectEvent):
        print("Yay i am connected :) :) :)")

    @Demands.GcodeEvent.on
    async def on_gcode(self, event: Demands.GcodeEvent):
        print("Gcode: %s", event.list)

        for gcode in event.list:
            if gcode[:4] == "M104":
                target = float(gcode[6:])

                print(f"Setting tool temperature to {target}")

                if target > 0.0:
                    self.printer.tool_temperatures[0].target = target
                else:
                    self.printer.tool_temperatures[0].target = None

            if gcode[:4] == "M140":
                target = float(gcode[6:])

                print(f"Setting bed temperature to {target}")

                if target > 0.0:
                    self.printer.bed_temperature.target = target
                else:
                    self.printer.bed_temperature.target = None

    @Demands.FileEvent.on
    async def on_file(self, event: Demands.FileEvent):
        downloader = FileDownload(self.printer.file_progress, asyncio.get_event_loop())
        data = await downloader.download_as_bytes(event.url)

    @Demands.StartPrintEvent.on
    async def on_start_print(self, event: Demands.StartPrintEvent):
        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0


    async def printer_loop(self):
        self.tick_rate = 0.1
        # Update temperatures, printer status and so on with smoothing function
        while True:
            if self.printer.bed_temperature.target is None:
                target = 20.0

            else:
                target = self.printer.bed_temperature.target

            self.printer.bed_temperature.actual = expt_smooth(
                target,
                self.printer.bed_temperature.actual,
                0.05,
                self.tick_rate
            )

            if self.printer.tool_temperatures[0].target is None:
                target = 20.0

            else:
                target = self.printer.tool_temperatures[0].target

            self.printer.tool_temperatures[0].actual = expt_smooth(
                target,
                self.printer.tool_temperatures[0].actual,
                0.05,
                self.tick_rate
            )

            if self.printer.status == PrinterStatus.PRINTING:
                self.printer.job_info.progress += expt_smooth(
                    100.0,
                    0.01,
                    0.15,
                    self.tick_rate
                )

                if self.printer.job_info.progress > 100.0:
                    self.printer.status = PrinterStatus.IDLE
                    self.printer.job_info.started = False
                    self.printer.job_info.progress = 0.0

            await asyncio.sleep(self.tick_rate)