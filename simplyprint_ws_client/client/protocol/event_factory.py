from typing import Dict, Union, Type, Optional

from .demand_events import DemandEvent
from .server_events import ServerEvent


class EventFactory:
    # Construct hashmap of events (sub-hashmap for demands)
    _events: Dict[str, Union[Type[ServerEvent], Dict[str, Type[DemandEvent]]]] = {event.get_name(): event for event in
                                                                                  ServerEvent.__subclasses__() if
                                                                                  event.get_name() != DemandEvent}
    _events[DemandEvent]: Dict[str, Type[DemandEvent]] = {event.demand: event for event in DemandEvent.__subclasses__()}

    @classmethod
    def get_event(cls, name: str, demand: Optional[str] = None, data=None) -> ServerEvent:
        if data is None:
            data = {}

        if demand is None:
            return cls._events[name](name, data)
        else:
            return cls._events[DemandEvent][demand](name, demand, data)
