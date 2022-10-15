import asyncio
import time
import logging
import math

from simplyprint_ws_client import * 

def exponential_smoothing(new_value: float, old_value: float, alpha: float, dt: float) -> float:
    factor = 1 - math.exp(-dt * alpha)
    return old_value + factor * (new_value - old_value)

class VirtualPrinter(Client):
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.info.api = "Virtual"
        self.info.api_version = "0.1"
        self.info.client = "Virtual"
        self.info.client_version = "0.0.1-alpha"
        self.info.sentry_dsn = "https://a5aef1defa83433586dd0cf1c1fffe57@o1102514.ingest.sentry.io/6619552"
        self.info.development = True
        self.local_path = "virtual_local"

        self.virtual_tool_temperatures = [Temperature(20.0)]
        self.virtual_bed_temperature = Temperature(20.0)
        
        self.logger = logging.getLogger("simplyprint.VirtualPrinter")

        self.tick_rate: float = 2.0

    async def on_connect(self, _: ConnectEvent):
        self.logger.info("Connected to server")

    async def on_gcode(self, event: GcodeEvent):
        self.logger.info("Gcode: %s", event.list)

        for gcode in event.list:
            if gcode[:4] == "M104":
                target = float(gcode[6:])

                self.logger.info(f"Setting tool temperature to {target}")
                
                if target > 0.0:
                    self.virtual_tool_temperatures[0].target = target
                else:
                    self.virtual_tool_temperatures[0].target = None

            if gcode[:4] == "M140":
                target = float(gcode[6:])

                self.logger.info(f"Setting bed temperature to {target}")

                if target > 0.0:
                    self.virtual_bed_temperature.target = target
                else:
                    self.virtual_bed_temperature.target = None

    async def on_start_print(self, _: StartPrintEvent) -> None:
        self.status = PrinterStatus.PRINTING
        await asyncio.sleep(300.0)
        self.print_done() 

    def update(self, dt: float):
        if self.virtual_bed_temperature.target is None:
            target = 20.0
        else:
            target = self.virtual_bed_temperature.target

        self.virtual_bed_temperature.actual = exponential_smoothing(
            target, 
            self.virtual_bed_temperature.actual, 
            0.05, 
            dt
        )

        for tool in self.virtual_tool_temperatures:
            if tool.target is None:
                target = 20.0
            else:
                target = tool.target

            tool.actual = exponential_smoothing(target, tool.actual, 0.1, dt) 
    
    def run(self):
        self.start()

        while True: 
            dt: float = 1.0 / self.tick_rate

            time.sleep(dt)
            self.update(dt)

            self.tool_temperatures = self.virtual_tool_temperatures
            self.bed_temperature = self.virtual_bed_temperature

if __name__ == "__main__":
    printer = VirtualPrinter()
    printer.run()
