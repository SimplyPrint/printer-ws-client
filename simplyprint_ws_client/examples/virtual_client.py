import asyncio
import math

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.printer.firmware.name = "Prusa i3 MK1"
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
        downloader = FileDownload(self)
        _ = await downloader.download_as_bytes(event.cdn_url)
        self.printer.file_progress.state = FileProgressState.READY
        await self.on_start_print(event)

    @Demands.StartPrintEvent.on
    async def on_start_print(self, event: Demands.StartPrintEvent):
        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0

    @Demands.CancelEvent.on
    async def on_cancel_event(self, _):
        self.printer.status = PrinterStatus.CANCELLING
        self.printer.job_info.cancelled = True
        await asyncio.sleep(2)
        self.printer.status = PrinterStatus.OPERATIONAL

    async def init(self):
        self.printer.bed_temperature.actual = 20.0
        self.printer.tool_temperatures[0].actual = 20.0
        self.printer.status = PrinterStatus.OPERATIONAL
        # self.printer.job_info.progress = 50

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
                0.1,
                0.01,
                0.1,
            )

            if self.printer.job_info.progress >= 100.0:
                self.printer.status = PrinterStatus.OPERATIONAL
                self.printer.job_info.finished = True
                self.printer.job_info.progress = 100

    async def stop(self):
        pass
