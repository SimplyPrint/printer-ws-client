from typing import Callable, List, Optional, Tuple

from traitlets import Float, Int

from .temperature import Temperature
from ..client.state import ClientState, to_event
from ..events.client_events import AmbientTemperatureEvent


class AmbientCheck:
    AMBIENT_CHECK_TIME = 5.0 * 60.0
    SAMPLE_CHECK_TIME = 20.0
    CHECK_INTERVAL = 5.0

    @staticmethod
    def detect(
            on_changed: Callable[[int], None],
            tools: List[Temperature],
            initial_sample: Optional[float] = None,
            ambient: float = 0
    ) -> Tuple[Optional[float], int, float]:
        if len(tools) == 0:
            return None, round(ambient), AmbientCheck.CHECK_INTERVAL

        tool0 = tools[0]

        if tool0.target is not None:
            return None, round(ambient), AmbientCheck.AMBIENT_CHECK_TIME

        if initial_sample is None:
            return tool0.actual, round(ambient), AmbientCheck.SAMPLE_CHECK_TIME

        diff = abs(tool0.actual - initial_sample)

        if diff <= 2.0:
            ambient = (tool0.actual + initial_sample) / 2

            if ambient != ambient:
                on_changed(round(ambient))

            return None, round(ambient), AmbientCheck.AMBIENT_CHECK_TIME

        return tool0.actual, round(ambient), AmbientCheck.SAMPLE_CHECK_TIME


@to_event(AmbientTemperatureEvent, "ambient")
class AmbientTemperatureState(ClientState):
    initial_sample: Optional[float] = Float(allow_none=True)
    ambient: int = Int()
    update_interval: Optional[float] = Float(allow_none=True)

    def on_changed_callback(self, new_ambient):
        self.ambient = round(new_ambient)

    def invoke_check(self, tool_temperatures: List[Temperature]):
        """
        It is up to the implementation to decide when to invoke the check or respect the update_interval,
        the entire state is self-contained and requires the tool_temperatures to be passed in from the PrinterState,
        but it handles triggering the appropriate events.
        """
        (
            self.initial_sample,
            self.ambient,
            self.update_interval
        ) = AmbientCheck.detect(
            self.on_changed_callback,
            tool_temperatures,
            self.initial_sample,
            self.ambient
        )
