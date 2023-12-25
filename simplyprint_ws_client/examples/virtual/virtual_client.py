import asyncio
import math

from ...helpers.file_download import FileDownload
from ...state.printer import FileProgressState, PrinterStatus
from ...client import DefaultClient
from ...events import Events, Demands

from .virtual_config import VirtualConfig


def expt_smooth(target, actual, alpha, dt) -> float:
    return actual + (target - actual) * (1.0 - math.exp(-alpha * dt))

class VirtualClient(DefaultClient[VirtualConfig]):
    def __init__(self, config: VirtualConfig):
        super().__init__(config)

        self.set_info("Virtual Printer", "0.0.1")
        self.setup_sentry("https://a5aef1defa83433586dd0cf1c1fffe57@o1102514.ingest.sentry.io/6619552")

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
        print(event)
        downloader = FileDownload(self, asyncio.get_event_loop())
        data = await downloader.download_as_bytes(event.url)
        self.printer.file_progress.state = FileProgressState.READY

    @Demands.StartPrintEvent.on
    async def on_start_print(self, event: Demands.StartPrintEvent):
        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0

    async def init(self):
        self.printer.bed_temperature.actual = 20.0
        self.printer.tool_temperatures[0].actual = 20.0
        self.printer.status = PrinterStatus.OPERATIONAL

    async def tick(self):
        # Update temperatures, printer status and so on with smoothing function
        if self.printer.bed_temperature.target is None:
            target = 20.0
        else:
            target = self.printer.bed_temperature.target

        self.printer.bed_temperature.actual = expt_smooth(
            target,
            self.printer.bed_temperature.actual,
            0.05,
            0.1,
        )

        if self.printer.tool_temperatures[0].target is None:
            target = 20.0

        else:
            target = self.printer.tool_temperatures[0].target

        self.printer.tool_temperatures[0].actual = expt_smooth(
            target,
            self.printer.tool_temperatures[0].actual,
            0.05,
            0.1,
        )

        if self.printer.status == PrinterStatus.PRINTING:
            self.printer.job_info.progress += expt_smooth(
                100.0,
                0.01,
                0.01,
                0.1,
            )

            if self.printer.job_info.progress > 100.0:
                self.printer.status = PrinterStatus.OPERATIONAL
                self.printer.job_info.finished = True
                self.printer.job_info.progress = 100