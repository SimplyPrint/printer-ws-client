import asyncio
import math
import random

from simplyprint_ws_client.core.client import DefaultClient
from simplyprint_ws_client.core.config import PrinterConfig
from simplyprint_ws_client.core.state import FileProgressState, PrinterStatus
from simplyprint_ws_client.core.ws_protocol.messages import StreamMsg, GcodeDemandData, FileDemandData
from simplyprint_ws_client.shared.files.file_download import FileDownload

_TEST_IMAGE = "iVBORw0KGgoAAAANSUhEUgAAAeAAAAFoCAIAAAAAVb93AAAFMklEQVR4nOzWQQkCYRhFUZFpYAVzWcAAGsAONnFvJ3FtAZc/fJfhnARvdXnb8/Q4wF68bp/pCbDMcXoAAP8JNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRG3f+3l6AyxzeV+nJ8AyHjRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNECUQANECTRAlEADRAk0QJRAA0QJNEDULwAA//+/JAlAlWQCTwAAAABJRU5ErkJggg=="


class VirtualConfig(PrinterConfig):
    ...


def expt_smooth(target, actual, alpha, dt) -> float:
    return actual + (target - actual) * (1.0 - math.exp(-alpha * dt))


class VirtualClient(DefaultClient[VirtualConfig]):
    job_progress_alpha: float = 0.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.printer.firmware.name = "Virtual Printer Firmware"
        self.printer.firmware.version = "1.0.0"

        self.printer.set_info("Virtual Printer", "0.0.1")
        self.printer.set_extruder_count(4)

        self.printer.webcam_info.connected = True

        for i, mat in enumerate(self.printer.material_data):
            mat.ext = i
            mat.type = "PLA" if i in (0, 1) else "PETG"
            mat.color = "Black"
            mat.hex = "#000000"

    async def on_connected(self):
        _ = self
        print("Yay i am connected :) :) :)")

    async def on_webcam_test(self):
        self.printer.webcam_info.connected = True

    async def on_stream_off(self):
        self.printer.intervals.set("webcam", -1)

    async def on_webcam_snapshot(self):
        await self.printer.intervals.wait_for("webcam")
        await self.send(StreamMsg(_TEST_IMAGE))

    async def on_gcode(self, data: GcodeDemandData):
        print("Gcode: %s", data.list)

        for gcode in data.list:
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

    async def on_file(self, data: FileDemandData):
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
        await self.on_start_print(data)

    async def on_start_print(self, _):
        # self.job_progress_alpha = random.uniform(0.05, 0.1)

        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0
        # Calculate the time to finish the print using the progress rate
        self.printer.job_info.time = round(100.0 / self.job_progress_alpha)

        self.printer.bed_temperature.target = 60.0
        self.printer.tool_temperatures[0].target = 225.0

    async def on_cancel(self, _):
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

    async def tick(self, _):
        await self.send_ping()

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

    async def halt(self):
        pass

    async def teardown(self):
        pass
