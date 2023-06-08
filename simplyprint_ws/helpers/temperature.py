from traitlets import Float

from ..state import ClientState
from ..events.client_events import TemperatureEvent

class Temperature(ClientState):
    actual = Float()
    target = Float()

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