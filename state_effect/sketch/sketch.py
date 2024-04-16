from dataclasses import dataclass
from typing import Any


@dataclass
class Temperature:
    actual: float
    target: float


@dataclass
class PrinterRawState:
    name: str
    nozzle_temperature: float
    nozzle_target_temperature: float
    bed_temperature: float
    bed_target_temperature: float


def reduce(*args, **kwargs) -> Any:
    ...


def parent(*args, **kwargs) -> Any:
    ...


class PrinterTemperature:
    bed: Temperature = reduce(PrinterRawState.bed_temperature, PrinterRawState.bed_target_temperature,
                              lambda a, b: Temperature(a, b))
    nozzle: Temperature

# When a bounded variable changes it outputs the entire partial state anew, with information about what has changed.
# We process them in bundles, assuming the raw state is a very large state, then given a small or large update
# produce the minimal amount of correct events.

# Maybe keep track of sub events
