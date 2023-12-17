from typing import Type

from simplyprint_ws_client.events.client_events import ClientEvent
from simplyprint_ws_client.state.root_state import DEFAULT_EVENT, ClientState


def to_event(client_event: Type[ClientEvent], *names: str):
    """ 
    Map events from a ClientState class to its _event_mapping
    """

    def wrapper(cls: ClientState):
        if not issubclass(cls, ClientState):
            raise ValueError("to_event can only be used on subclasses of ClientState")

        if not hasattr(cls, "_event_mapping"):
            cls._event_mapping = {}
 
        if not names:
            cls._event_mapping[DEFAULT_EVENT] = client_event
            return cls
        
        for name in names:
            cls._event_mapping[name] = client_event

        return cls 

    return wrapper