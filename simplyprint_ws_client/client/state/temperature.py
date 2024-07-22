from traitlets import Float

from .state import ClientState, to_event
from ..protocol.client_events import TemperatureEvent


class _DefaultFloatSentinel(float):
    def __eq__(self, other):
        return isinstance(other, _DefaultFloatSentinel)


_float_sentinel = _DefaultFloatSentinel()


@to_event(TemperatureEvent, "actual", "target")
class Temperature(ClientState):
    actual: float = Float(default_value=_float_sentinel)
    target: float = Float(default_value=_float_sentinel)

    @property
    def rounded_actual(self) -> int:
        return round(self.actual) if self.actual is not _float_sentinel else 0

    @property
    def rounded_target(self) -> int:
        return round(self.target) if self.target is not _float_sentinel else 0

    def __eq__(self, other) -> bool:
        if not isinstance(other, Temperature):
            return False

        return self.rounded_actual == other.rounded_actual and self.rounded_target == other.rounded_target

    def __repr__(self):
        return f"Temperature(actual={self.rounded_actual}, target={self.rounded_target})"

    def is_heating(self) -> bool:
        if self.target is _float_sentinel:
            return False

        return self.rounded_actual != self.rounded_target

    def to_list(self):
        return [self.rounded_actual] + (([self.rounded_target]) if self.target is not _float_sentinel else [])
