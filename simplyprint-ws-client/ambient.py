import asyncio
from .printer_state import Printer, Temperature
from typing import Callable, List, Optional

AMBIENT_CHECK_TIME = 5.0 * 60.0
SAMPLE_CHACK_TIME = 20.0
CHECK_INTERVAL = 5.0

class AmbientCheck:
    initial_sample: Optional[float] = None
    ambient: float = 0
    changed: Callable[[int], None] = lambda _: None
    update_interval: float = AMBIENT_CHECK_TIME

    def __init__(self, changed: Callable[[int], None]):
        self.changed = changed

    # detects ambient temperature
    # uses the algorithm defined in SimplyPrint-OctoPrint
    def detect(self, tools: List[Temperature]):
        if len(tools) == 0:
            self.initial_sample = None
            self.update_interval = CHECK_INTERVAL
            return

        tool0 = tools[0]

        if not tool0.target is None:
            self.initial_sample = None
            self.update_interval = AMBIENT_CHECK_TIME
            return

        if self.initial_sample is None:
            self.initial_sample = tool0.actual
            self.update_interval = SAMPLE_CHACK_TIME
        else:
            diff = abs(tool0.actual - self.initial_sample)
            if diff <= 2.0:
                last_ambient = self.ambient
                self.ambient = (tool0.actual + self.initial_sample) / 2
                self.initial_sample = None
                self.update_interval = AMBIENT_CHECK_TIME

                if round(last_ambient) != round(self.ambient):
                    self.changed(round(self.ambient))
            else:
                self.initial_sample = tool0.actual
                self.update_interval = SAMPLE_CHACK_TIME

    # runs the ambient check in a loop
    # spawned on start
    async def run_loop(self, printer: Printer):
        while True:
            self.detect(printer.tool_temperatures)
            await asyncio.sleep(self.update_interval)
