from .printer_state import Intervals

from typing import (
    Callable, 
    Dict,
    Any,
)

class EventCallbacks:
    def __init__(self):
        self.on_new_token: Callable[[NewTokenEvent], None] = lambda _: None
        self.on_connect: Callable[[ConnectEvent], None] = lambda _: None
        self.on_pause: Callable[[PauseEvent], None] = lambda _: None

class Event:
    def __init__(self):        
        pass

class NewTokenEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        print(data)
        self.short_id: str = data.get("short_id", "")
        self.token: str = data.get("token", "")

class ConnectEvent(Event):
    def __init__(self, data: Dict[str, Any]):
        self.in_set_up: bool = data.get("in_set_up", 0) == 1
        self.intervals: Intervals = Intervals(data.get("interval", {}))

        pass

class PauseEvent(Event):
    def __init__(self):
        pass
