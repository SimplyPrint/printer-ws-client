import logging

from . import events as Events
from . import demands as Demands
from . import client_events as ClientEvents
from .events import ServerEvent
from .demands import DemandEvent
from .client_events import ClientEvent

from typing import Dict, Type, Union, Any, Optional

# Construct hashmap of events (sub-hashmap for demands)
events: Dict[str, Union[Type[ServerEvent], Dict[str, Type[DemandEvent]]]] = { event.name: event for event in ServerEvent.__subclasses__() if event.name != DemandEvent }
events[DemandEvent]: Dict[str, Type[DemandEvent]] = { demand: event for event in DemandEvent.__subclasses__() for demand in (event.demand if isinstance(event.demand, list) else [event.demand]) }

def get_event(name: str, demand: Optional[str] = None, data: Dict[str, any] = {}) -> ServerEvent:
    """
    Raises:
        ValueError: If the event does not exist
    """
    if demand is None:
        return events[name](name, data)
    else:
        return events[DemandEvent][demand](name, demand, data)