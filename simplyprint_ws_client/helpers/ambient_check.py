from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..client.state import Temperature


class AmbientCheck:
    AMBIENT_CHECK_TIME = 5.0 * 60.0
    SAMPLE_CHECK_TIME = 20.0
    CHECK_INTERVAL = 5.0

    @staticmethod
    def detect(
            on_changed: Callable[[int], None],
            tools: List['Temperature'],
            initial_sample: Optional[float] = None,
            ambient: float = 0
    ) -> Tuple[Optional[float], int, float]:
        if len(tools) == 0:
            return None, round(ambient), AmbientCheck.CHECK_INTERVAL

        tool0 = tools[0]

        if tool0.target:
            return None, round(ambient), AmbientCheck.AMBIENT_CHECK_TIME

        if initial_sample is None:
            return tool0.actual, round(ambient), AmbientCheck.SAMPLE_CHECK_TIME

        diff = abs(tool0.actual - initial_sample)

        if diff <= 2.0:
            new_ambient = (tool0.actual + initial_sample) / 2

            if ambient != new_ambient:
                on_changed(round(new_ambient))

            return None, round(new_ambient), AmbientCheck.AMBIENT_CHECK_TIME

        return tool0.actual, round(ambient), AmbientCheck.SAMPLE_CHECK_TIME
