from typing import Type, Union

from simplyprint_ws_client.events.event_listeners import ListenerUniqueness


class EventTraits:
    def __eq__(self: Union[Type['Event'], 'Event'], other: object) -> bool:
        if isinstance(other, str):
            return self.get_name() == other

        if isinstance(other, Event) or isinstance(other, EventType):
            return self.get_name() == other.get_name()

        return self is other

    def __str__(self: Union[Type['Event'], 'Event']) -> str:
        return self.get_name()

    def __hash__(self: Union[Type['Event'], 'Event']) -> int:
        return hash(self.__name__ if isinstance(self, type) else self.__class__.__name__)


class EventType(EventTraits, type):
    @classmethod
    def get_name(cls):
        raise NotImplementedError()


class Event(EventTraits, metaclass=EventType):
    """
    Base event class for type-hinting, not required to be used.
    """

    __stopped: bool = False

    @classmethod
    def get_name(cls) -> str:
        return cls.__name__

    # Allow for propagation control of events.
    def is_stopped(self) -> bool:
        return self.__stopped

    def stop_event(self) -> None:
        self.__stopped = True

    @classmethod
    def on(cls, generic=False, priority: int = 0, unique: ListenerUniqueness = ListenerUniqueness.NONE):
        """Use as decorator to mark functions as event handlers"""

        def decorator(func):
            func._event_class = cls
            func._event_generic = generic
            func._event_priority = priority
            func._event_unique = unique
            return func

        return decorator
