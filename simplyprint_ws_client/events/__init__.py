from typing import Any, Dict, Optional, Type, Union

from . import client_events as ClientEvents
from . import demands as Demands
from . import server_events as Events
from .demands import DemandEvent
from .server_events import ServerEvent

# Construct hashmap of events (sub-hashmap for demands)
_events: Dict[str, Union[Type[ServerEvent], Dict[str, Type[DemandEvent]]]] = { event.get_name(): event for event in ServerEvent.__subclasses__() if event.get_name() != DemandEvent }
_events[DemandEvent]: Dict[str, Type[DemandEvent]] = { event.demand: event for event in DemandEvent.__subclasses__() }

def get_event(name: str, demand: Optional[str] = None, data: Dict[str, any] = {}) -> ServerEvent:
    """
    Raises:
        ValueError: If the event does not exist
    """
    if demand is None:
        return _events[name](name, data)
    else:
        return _events[DemandEvent][demand](name, demand, data)
