import asyncio
import heapq
from typing import (Callable, Dict, Generator, Generic, Hashable, List,
                    Optional, TypeVar, Union, get_args)

from .event import Event

TEvent = TypeVar('TEvent', bound=object)


class EventBusListener:
    priority: int
    handler: Callable
    is_async: bool

    async def __call__(self, *args, **kwargs):
        if not self.is_async:
            return self.handler(*args, **kwargs)

        return await self.handler(*args, **kwargs)

    def __init__(self, priority: int, handler: Callable) -> None:
        self.priority = priority
        self.handler = handler
        self.is_async = asyncio.iscoroutinefunction(handler)

    def __lt__(self, other: 'EventBusListener') -> bool:
        return self.priority < other.priority

    def __eq__(self, other: Union['EventBusListener', Callable]) -> bool:
        if isinstance(other, EventBusListener):
            return self.handler == other.handler

        return self.handler == other

    def __hash__(self) -> int:
        return hash(self.handler)


class EventBusListeners:
    listeners: List[Callable]

    def __init__(self) -> None:
        self.listeners = []

    def add(self, listener: Callable, priority: int) -> None:
        heapq.heappush(self.listeners, (priority,
                       EventBusListener(priority, listener)))

    def remove(self, listener: Callable) -> None:
        for i, (_, reg_listener) in reversed(list(enumerate(self.listeners))):
            if reg_listener == listener:
                del self.listeners[i]
                break

    def __iter__(self) -> Generator[EventBusListener, None, None]:
        for _, listener in self.listeners:
            yield listener

    def __len__(self) -> int:
        return len(self.listeners)


class EventBus(Generic[TEvent]):
    event_klass: TEvent
    listeners: Dict[Hashable, EventBusListeners]

    def __init__(self) -> None:
        self.listeners = {}

        # Extract the generic type from the class otherwise
        # fallback to the default Event class
        try:
            self.event_klass = get_args(self.__class__.__orig_bases__[0])[0]
        except:
            self.event_klass = Event

        if not isinstance(self.event_klass, type):
            self.event_klass = Event

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs):
        if not event in self.listeners:
            return

        if isinstance(event, self.event_klass):
            args = (event, *args)

        for listener in self.listeners[event]:
            # The listener may return the modified event parameter in
            # the case the emitted event was of a event class type.
            # this will replace the event parameter with the modified one.
            ret = await listener(*args, **kwargs)

            if (
                ret is not None
                and isinstance(event, self.event_klass)
                and isinstance(ret, self.event_klass)
            ):
                args = (ret, *args[1:])

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs):
        """
        Skip all async listeners and only emit to synchronous listeners.
        """

        if not event in self.listeners:
            return

        if isinstance(event, self.event_klass):
            args = (event, *args)

        for listener in self.listeners[event]:
            if listener.is_async:
                continue

            ret = listener.handler(*args, **kwargs)

            if (
                ret is not None
                and isinstance(event, self.event_klass)
                and isinstance(ret, self.event_klass)
            ):
                args = (ret, *args[1:])

    def emit_task(self, event: Union[Hashable, TEvent], *args, **kwargs) -> asyncio.Task:
        """Allows for synchronous emitting of events. Useful cross-thread communication."""
        return asyncio.create_task(self.emit(event, *args, **kwargs))

    def emit_wrap(self, event: Union[Hashable, TEvent], sync_only = False):
        """
        Returns a curried function that emits the given event with any arguments passed to it.
        
        When sync_only is specified the function will only invoke synchronous listeners. 
        """
        
        emit_func = self.emit_sync if sync_only else self.emit
        return lambda *args, **kwargs: emit_func(event, *args, **kwargs)
        
    def on(self, event_type: Hashable, listener: Optional[Callable] = None, priority: int = 0, generic: bool = False):
        if listener is None:
            return lambda listener: self._register_listeners(event_type, listener, priority, generic)

        return self._register_listeners(event_type, listener, priority, generic)

    def _register_listeners(self, event_type: Hashable, listener: Callable, priority=0, generic: bool = False) -> Callable:
        """
        Registers all listerners for a generic type given the type is an event type,
        otherwise wraps a single register call.
        """

        if not generic or not issubclass(event_type, self.event_klass):
            self._register_listener(event_type, listener, priority)
            return listener

        for klass in self._iterate_subclasses(event_type):
            self._register_listener(klass, listener, priority)

        return listener

    def _register_listener(self, event_type: Hashable, listener: Callable, priority=0) -> None:
        """Registers a single listener for a given event type."""

        if event_type not in self.listeners:
            self.listeners[event_type] = EventBusListeners()

        self.listeners[event_type].add(listener, priority=priority)

    def _iterate_subclasses(self, klass: type) -> Generator[type, None, None]:
        """Perform class introspection to construct listeners generically"""
        if not issubclass(klass, self.event_klass):
            raise TypeError(
                f"Expected type of {self.event_klass} but got {klass}")

        for subclass in klass.__subclasses__():
            yield from self._iterate_subclasses(subclass)
            yield subclass

        # Include the class itself
        yield klass
