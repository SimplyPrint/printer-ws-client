import time
import logging
import math

from printer_ws_client import * 

def exponential_smoothing(new_value: float, old_value: float, alpha: float, dt: float) -> float:
    factor = 1 - math.exp(-dt * alpha)
    return old_value + factor * (new_value - old_value)

class VirtualPrinter(Client):
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.virtual_tool_temperatures = [Temperature(20.0)]
        self.virtual_bed_temperature = Temperature(20.0)
        
        self.logger = logging.getLogger("simplyprint.VirtualPrinter")

        self.id = "385"
        self.token = "804b58-8a9ed5-e83c37-a73306-6dabd7"

    def on_connect(self, _: ConnectEvent):
        self.logger.info("Connected to server")

    def on_gcode(self, event: GcodeEvent):
        self.logger.info("Gcode: %s", event.list)
        if event.list[0][:4] == "M104":
            target = float(event.list[0][6:])

            self.logger.info(f"Setting tool temperature to {target}")
            
            if target > 0.0:
                self.virtual_tool_temperatures[0].target = target
            else:
                self.virtual_tool_temperatures[0].target = None

    def update(self, dt: float):
        for tool in self.virtual_tool_temperatures:
            if tool.target is None:
                target = 20.0
            else:
                target = tool.target

            tool.actual = exponential_smoothing(target, tool.actual, 0.1, dt) 
    
    def run(self):
        self.start()

        while True: 
            time.sleep(0.5)  
            self.update(0.5)

            self.tool_temperatures = self.virtual_tool_temperatures
            self.bed_temperature = self.virtual_bed_temperature

if __name__ == "__main__":
    printer = VirtualPrinter()
    printer.run()
