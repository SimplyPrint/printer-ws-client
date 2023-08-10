from .events import ServerEvent
from .demands import DemandEvent

from typing import Dict, Type, Union, Any, Optional

# Construct hashmap of events (sub-hashmap for demands)
_events: Dict[str, Union[Type[ServerEvent], Dict[str, Type[DemandEvent]]]] = { event.name: event for event in ServerEvent.__subclasses__() if event.name != DemandEvent }
_events[DemandEvent]: Dict[str, Type[DemandEvent]] = { demand: event for event in DemandEvent.__subclasses__() for demand in (event.demand if isinstance(event.demand, list) else [event.demand]) }

def get_event(name: str, demand: Optional[str] = None, data: Dict[str, any] = {}) -> ServerEvent:
    """
    Raises:
        ValueError: If the event does not exist
    """
    if demand is None:
        return _events[name](name, data)
    else:
        return _events[DemandEvent][demand](name, demand, data)
