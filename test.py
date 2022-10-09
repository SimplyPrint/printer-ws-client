import time
import logging
import math

from printer_ws_client import * 

def exponential_smoothing(new_value: float, old_value: float, alpha: float, dt: float) -> float:
    factor = 1 - math.exp(-dt * alpha)
    return old_value + factor * (new_value - old_value)

class VirtualPrinter:
    def __init__(self):
        logging.basicConfig(level=logging.DEBUG)

        self.client: Client = Client()

        self.tool_temperatures: List[Temperature] = [Temperature(20.0)]
        self.bed_temperature: Temperature = Temperature(20.0)
        
        self.client.callbacks.on_gcode = self.on_gcode
        self.logger = logging.getLogger("simplyprint.VirtualPrinter")

        self.client.set_id("385")
        self.client.set_token("804b58-8a9ed5-e83c37-a73306-6dabd7")
        self.client.start()

    def on_gcode(self, event: GcodeEvent):
        self.logger.info("Gcode: %s", event.list)
        if event.list[0][:4] == "M104":
            target = float(event.list[0][6:])

            self.logger.info(f"Setting tool temperature to {target}")
            
            if target > 0.0:
                self.tool_temperatures[0].target = target
            else:
                self.tool_temperatures[0].target = None

    def update(self, dt: float):
        for tool in self.tool_temperatures:
            if tool.target is None:
                target = 20.0
            else:
                target = tool.target

            tool.actual = exponential_smoothing(target, tool.actual, 0.1, dt)
    
    def run(self):
        self.client.start()

        while True: 
            time.sleep(0.5)  
            self.update(0.5)
            self.client.set_temperatures(self.tool_temperatures, self.bed_temperature);


if __name__ == "__main__":
    printer = VirtualPrinter()
    printer.run()
