from typing import Optional

from traitlets import Float

from ..events.client_events import TemperatureEvent
from ..state import ClientState


class Temperature(ClientState):
    actual: Optional[float] = Float()
    target: Optional[float] = Float(allow_none=True)

    event_map = {
        "actual": TemperatureEvent,
        "target": TemperatureEvent,
    }

    def __eq__(self, other) -> bool:
        if not isinstance(other, Temperature):
            return False

        return self.actual == other.actual and self.target == other.target

    def is_heating(self) -> bool:
        if self.target is None:
            return False

        return round(self.actual) != round(self.target)
    
    def to_list(self):
        return [round(self.actual)] + ([round(self.target)] if self.target is not None else [])