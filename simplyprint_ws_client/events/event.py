class EventTraits:
    def __eq__(cls, other: object) -> bool:
        if isinstance(other, str): return cls.get_name() == other
        if isinstance(other, Event): return cls.get_name() == other.get_name()
        if isinstance(other, EventTraits): return cls.get_name() == other.get_name()
        return False
    
    def __str__(cls) -> str:
        return cls.get_name()
    
    def __hash__(cls) -> int:
        return hash(cls.__name__ if isinstance(cls, type) else cls.__class__.__name__)

class EventType(EventTraits, type):
    ...

class Event(EventTraits, metaclass=EventType):
    """
    Base event class for type-hinting, not required to be used.
    """
    
    @classmethod
    def get_name(cls) -> str:
        return cls.__name__
    
    # Allow for propegation control of events.
    def is_stopped(self) -> bool:
        return hasattr(self, "_stopped") and self._stopped
    
    def stop_event(self) -> None:
        self._stopped = True