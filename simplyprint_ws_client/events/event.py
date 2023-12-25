class EventTraits:
    def __str__(cls):
        return cls.get_name()
    
    def __repr__(cls) -> str:
        return f"<{cls.__class__.__base__.__name__} {cls.get_name()}>"
    
    def __eq__(cls, other: object) -> bool:
        if isinstance(other, str): return cls.get_name() == other
        if isinstance(other, Event): return cls.get_name() == other.get_name()
        if isinstance(other, EventTraits): return cls.get_name() == other.get_name()
        return False
    
    def __hash__(cls) -> int:
        if cls.get_name() is None: return hash(cls.__class__)

        return hash(cls.get_name())

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