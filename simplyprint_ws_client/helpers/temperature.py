from typing import Optional

from traitlets import Float

from ..client.state import ClientState, to_event
from ..events.client_events import TemperatureEvent


@to_event(TemperatureEvent, "actual", "target")
class Temperature(ClientState):
    actual: float = Float()
    target: Optional[float] = Float(allow_none=True)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Temperature):
            return False

        return round(self.actual) == round(other.actual) and round(self.target) == round(other.target)

    def is_heating(self) -> bool:
        if self.target is None:
            return False

        return round(self.actual) != round(self.target)

    def to_list(self):
        return [round(self.actual)] + ([round(self.target)] if self.target is not None else [])
