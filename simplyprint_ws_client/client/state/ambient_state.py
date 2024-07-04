from typing import Optional, TYPE_CHECKING, List

from traitlets import Float, Int

from .state import ClientState, to_event
from ..protocol.client_events import AmbientTemperatureEvent
from ...helpers.ambient_check import AmbientCheck

if TYPE_CHECKING:
    from .temperature import Temperature


@to_event(AmbientTemperatureEvent, "ambient")
class AmbientTemperatureState(ClientState):
    initial_sample: Optional[float] = Float(allow_none=True)
    ambient: int = Int()
    update_interval: Optional[float] = Float(allow_none=True)

    def on_changed_callback(self, new_ambient):
        self.ambient = round(new_ambient)

    def invoke_check(self, tool_temperatures: List['Temperature']):
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
