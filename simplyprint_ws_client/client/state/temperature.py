from typing import Optional

from traitlets import Float

from .state import ClientState, to_event
from ..protocol.client_events import TemperatureEvent


@to_event(TemperatureEvent, "actual", "target")
class Temperature(ClientState):
    actual: float = Float()
    target: Optional[float] = Float(allow_none=True)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Temperature):
            return False

        return round(self.actual) == round(other.actual) and round(self.target) == round(other.target)

    def __repr__(self):
        return f"Temperature(actual={self.actual}, target={self.target})"

    def is_heating(self) -> bool:
        if not self.target:
            return False

        return round(self.actual) != round(self.target)

    def to_list(self):
        return [round(self.actual)] + ([round(self.target)] if self.target else [])
