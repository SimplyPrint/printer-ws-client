import logging
import math
import asyncio
import threading

from simplyprint_ws_client.helpers.file_download import FileDownload
from simplyprint_ws_client.helpers.sentry import Sentry
from simplyprint_ws_client.helpers.temperature import Temperature
from simplyprint_ws_client.client import DefaultClient
from simplyprint_ws_client.config import Config, ConfigManager

from simplyprint_ws_client.events import events as Events
from simplyprint_ws_client.events import demands as Demands
from simplyprint_ws_client.multiplexer import Multiplexer, MultiplexerMode

from simplyprint_ws_client.state.printer import PrinterStatus

def expt_smooth(target, actual, alpha, dt):
    return actual + (target - actual) * (1.0 - math.exp(-alpha * dt))

class VirtualClient(DefaultClient):
    def __init__(self, config: Config):
        super().__init__(config)

        self.sentry = Sentry()
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
        print(event)
        downloader = FileDownload(self.printer.file_progress, asyncio.get_event_loop())
        data = await downloader.download_as_bytes(event.url)

    @Demands.StartPrintEvent.on
    async def on_start_print(self, event: Demands.StartPrintEvent):
        self.printer.status = PrinterStatus.PRINTING
        self.printer.job_info.started = True
        self.printer.job_info.progress = 0.0


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


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    config = ConfigManager.get_config(17120) or Config(id=0, token="0")
    client = VirtualSuperClient(config)
    mp = Multiplexer(MultiplexerMode.SINGLE, config)
    mp.allow_setup = True
    mp.add_client(client)
    threading.Thread(target=mp.start).start()
    asyncio.run(client.printer_loop())
