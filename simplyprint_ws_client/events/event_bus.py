import asyncio
import heapq

from abc import ABC, abstractmethod
from typing import Callable, Dict, Generator, Generic, Hashable, List, Optional, Type, TypeVar, Tuple, get_args

class EventTraits:
    def __str__(cls):
        return cls.get_name()
    
    def __repr__(cls) -> str:
        return f"<{cls.__class__} {cls.get_name()}>"
    
    def __eq__(cls, other: object) -> bool:
        if isinstance(other, str): return cls.get_name() == other
        if isinstance(other, Event): return cls.get_name() == other.get_name()
        if isinstance(other, EventTraits): return cls.get_name() == other.get_name()
        return False
    
    def __hash__(cls) -> int:
        if cls.get_name() is None: return hash(cls.__class__)

        return hash(cls.get_name())

class EventType(type, EventTraits):
    def __repr__(cls) -> str:
        return f"<{cls.__class__} {cls}>"

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

TEvent = TypeVar('TEvent', bound=object)

class EventBus(Generic[TEvent]):
    _generic_class: Type[TEvent]

    handlers: Dict[Hashable, List[Tuple[int, Callable]]]
    _generic_handlers: Dict[str, List[Tuple[int, Callable]]]

    def __init__(self):
        self.handlers = {}
        self._generic_handlers = {}

        try:
            self._generic_class = get_args(self.__class__.__orig_bases__[0])[0]
        except:
            self._generic_class = Event

        if not isinstance(self._generic_class, type):
            self._generic_class = Event

    def on(self, event: Hashable, handler: Optional[Callable] = None, priority: int = 0):
        return self._register_handler(self.handlers, event, handler, priority)
    
    def on_generic(self, event: Hashable, handler: Optional[Callable] = None, priority: int = 0):
        return self._register_handler(self._generic_handlers, event, handler, priority)

    def _register_handler(self, handlers: List, event: Hashable, handler: Optional[Callable] = None, priority: int = 0):
        if event not in handlers:
            handlers[event] = []

        def wrapper(func):
            try:
                heapq.heappush(handlers[event], (priority, id(func), func))
            except TypeError:
                pass

            return func
        
        if handler is None:
            return wrapper
        else:
            return wrapper(handler)        

    def off(self, event: Hashable, handler: Callable):
        for handler in self._get_event_handlers(event):
            if handler != handler:
                continue

            for i, (_, _, handler) in reversed(list(enumerate(self.handlers[event]))):
                if handler == handler:
                    del self.handlers[event][i]
                    break

            for i, (_, _, handler) in reversed(list(enumerate(self._generic_handlers[event]))):
                if handler == handler:
                    del self._generic_handlers[event][i]
                    break

    def _merge_args(self, handled, args):
        if isinstance(handled, tuple):
            args = handled + args
        else:
            args = args + (handled,)

        return args
    
    def _is_allowed_event(self, event: Hashable):
        return isinstance(event, self._generic_class) or event in self.handlers
    
    def _get_event_handlers(self, event: Hashable) -> Generator[Callable, None, None]:
        for _, _, handler in self.handlers.get(event, []):
            yield handler

        # First handle generic handlers
        for cls, handlers in self._generic_handlers.items():
            if isinstance(event, cls):
                for _, _, handler in handlers:
                    yield handler
        
    async def emit(self, event: Hashable, *args, **kwargs):
        is_event_obj = isinstance(event, self._generic_class)

        if is_event_obj and not event in args:
            args = self._merge_args(event, args)
        
        for handler in self._get_event_handlers(event):                 
            handled = None

            if asyncio.iscoroutinefunction(handler):
                handled = await handler(*args, **kwargs)
            else:
                handled = handler(*args, **kwargs)

            if is_event_obj and event.is_stopped():
                break

            if handled is not None:
                args = self._merge_args(handled, args)
        
    def clear(self, event: Optional[Hashable] = None):
        if event is None:
            self.handlers.clear()
        elif event in self.handlers:
            del self.handlers[event]

