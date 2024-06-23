import asyncio
import math
import random

from simplyprint_ws_client.client.client import DefaultClient
from simplyprint_ws_client.client.config import PrinterConfig
from simplyprint_ws_client.client.state.printer import FileProgressState, PrinterStatus
from simplyprint_ws_client.events import Events, Demands
from simplyprint_ws_client.helpers.file_download import FileDownload


class VirtualConfig(PrinterConfig):
    ...


def expt_smooth(target, actual, alpha, dt) -> float:
    return actual + (target - actual) * (1.0 - math.exp(-alpha * dt))


class VirtualClient(DefaultClient[VirtualConfig]):
    job_progress_alpha: float = 0.05

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.printer.firmware.name = "Virtual Printer Firmware"
        self.printer.firmware.version = "1.0.0"
        self.set_info("Virtual Printer", "0.0.1")

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
                    self.printer.tool_temperatures[0].target = 0.0

            if gcode[:4] == "M140":
                target = float(gcode[6:])

                print(f"Setting bed temperature to {target}")

                if target > 0.0:
                    self.printer.bed_temperature.target = target
                else:
                    self.printer.bed_temperature.target = 0.0

    @Demands.FileEvent.on
    async def on_file(self, event: Demands.FileEvent):
        downloader = FileDownload(self)

        # fake self.printer.file_progress.percent using event.file_size
        self.printer.file_progress.state = FileProgressState.DOWNLOADING
        self.printer.file_progress.percent = 0.0

        alpha = random.uniform(0.1, 0.5)

        while self.printer.file_progress.percent < 100.0:
            self.printer.file_progress.percent = max(100.0, expt_smooth(
                105.0,
                self.printer.file_progress.percent,
                alpha,
                0.1,
            ))
            await asyncio.sleep(0.1)

        self.printer.file_progress.state = FileProgressState.READY
        await self.on_start_print(event)

    @Demands.StartPrintEvent.on
    async def on_start_print(self, _):
        self.job_progress_alpha = random.uniform(0.05, 0.1)

        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0
        # Calculate the time to finish the print using the progress rate
        self.printer.job_info.time = round(100.0 / self.job_progress_alpha)

        self.printer.bed_temperature.target = 60.0
        self.printer.tool_temperatures[0].target = 225.0

    @Demands.CancelEvent.on
    async def on_cancel_event(self, _):
        self.printer.status = PrinterStatus.CANCELLING
        self.printer.job_info.cancelled = True
        await asyncio.sleep(2)
        self.printer.status = PrinterStatus.OPERATIONAL

        self.printer.bed_temperature.target = 0.0
        self.printer.tool_temperatures[0].target = 0.0

    async def init(self):
        self.printer.bed_temperature.actual = 20.0
        self.printer.bed_temperature.target = 0.0
        self.printer.tool_temperatures[0].actual = 20.0
        self.printer.tool_temperatures[0].target = 0.0
        self.printer.status = PrinterStatus.OPERATIONAL

    async def tick(self):
        # Update temperatures, printer status and so on with smoothing function
        if self.printer.bed_temperature.target:
            target = self.printer.bed_temperature.target

            self.printer.bed_temperature.actual = expt_smooth(
                target,
                self.printer.bed_temperature.actual,
                15,
                0.1,
            )

        else:
            self.printer.bed_temperature.actual = 20.0

        if self.printer.tool_temperatures[0].target:
            target = self.printer.tool_temperatures[0].target

            self.printer.tool_temperatures[0].actual = expt_smooth(
                target,
                self.printer.tool_temperatures[0].actual,
                15,
                0.1,
            )

        else:
            self.printer.tool_temperatures[0].actual = 20.0

        self.printer.ambient_temperature.ambient = 20

        if self.printer.status == PrinterStatus.PRINTING and not self.printer.is_heating():
            self.printer.job_info.progress = expt_smooth(
                100.0,
                self.printer.job_info.progress,
                self.job_progress_alpha,
                0.1,
            )

            self.printer.job_info.time = round(100.0 / self.job_progress_alpha)

            if round(self.printer.job_info.progress) >= 100.0:
                self.printer.job_info.finished = True
                self.printer.job_info.progress = 100
                self.printer.status = PrinterStatus.OPERATIONAL

                self.printer.bed_temperature.target = 0.0
                self.printer.tool_temperatures[0].target = 0.0

    async def stop(self):
        pass
