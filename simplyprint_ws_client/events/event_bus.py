import asyncio
import heapq
from asyncio import AbstractEventLoop
from typing import (Callable, Dict, Generator, Generic, Hashable, List,
                    Optional, TypeVar, Union, get_args, Type, Any, Tuple)

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
    listeners: List[Tuple[int, EventBusListener]]

    def __init__(self) -> None:
        self.listeners = []

    def add(self, listener: Callable, priority: int) -> None:
        if self.contains(listener):
            raise ValueError("Listener already registered")

        heapq.heappush(self.listeners, (priority,
                                        EventBusListener(priority, listener)))

    def remove(self, listener: Callable) -> None:
        for i, (_, reg_listener) in reversed(list(enumerate(self.listeners))):
            if reg_listener == listener:
                del self.listeners[i]
                break

    def contains(self, listener: Callable) -> bool:
        for _, reg_listener in self.listeners:
            if reg_listener == listener:
                return True

        return False

    def __iter__(self) -> Generator[EventBusListener, None, None]:
        for _, listener in self.listeners:
            yield listener

    def __len__(self) -> int:
        return len(self.listeners)


class EventBus(Generic[TEvent]):
    loop_factory: Callable[[], AbstractEventLoop]
    listeners: Dict[Hashable, EventBusListeners]
    event_klass: Type[TEvent]

    def __init__(self, loop_factory: Optional[Callable[[], AbstractEventLoop]] = None) -> None:
        self.loop_factory = loop_factory or asyncio.get_running_loop
        self.listeners = {}

        # Extract the generic type from the class otherwise
        # fallback to the default Event class
        try:
            self.event_klass = get_args(self.__class__.__orig_bases__[0])[0]
        except (AttributeError, KeyError, IndexError):
            self.event_klass = Event

        if not isinstance(self.event_klass, type):
            self.event_klass = Event

    def update_args(
            self,
            event: Union[Hashable, TEvent],
            args: Tuple[Any, ...],
            returned_args: Union[Tuple[Any, ...], Any] = None
    ) -> Tuple[Any, ...]:
        """
        This function transforms the arguments returned by an event listener
        into the arguments that will be passed to the next listener.

        - If `returned_args` is None, the original arguments will be used.
        - If `returned_args` is an event of type klass, it will replace the original event.
        - If `returned_args` is something that is not an event, the original arguments will be replaced.
        - If `returned_args` is an empty tuple, the original arguments will be replaced.
        - If `returned_args` is a tuple that includes an event of type klass, it will replace everything.

        Given an event listener function like so:

        ```
        def listener(event: Event, *args, **kwargs) -> Event:
            # Do something with event
            return event
        ```

        The returned event will now take precedence over the original event.

        Given an event listener function like so:

        ```
        def listener(event: Event, *args, **kwargs) -> Tuple[Event, ...]:
            # Do something with event and return more arguments
            return event, ...
        ```

        Then returned_args will replace the entire argument list.
        """
        if returned_args is None:
            return args

        # If the event is an instance of the event class
        # it is always the first element of args.
        event_is_first = isinstance(event, self.event_klass) and len(args) > 0 and args[0] == event

        if not isinstance(returned_args, tuple):
            # The listener may return the modified event parameter in
            # the case the emitted event was of an event class type.
            # this will replace the event parameter with the modified one.
            if event_is_first:
                return (returned_args, *args[1:]) if isinstance(returned_args, self.event_klass) else (
                    event, returned_args)

            # Otherwise replace the entire argument list with the returned data.
            return (returned_args,)

        # If we return an empty tuple, we want to replace the entire argument list.
        if len(returned_args) == 0:
            return (event,) if event_is_first else ()

        # Now we have to handle the case where the listener returns a tuple.
        if event_is_first:
            return returned_args if isinstance(returned_args[0], self.event_klass) else (event, *returned_args)

        # As a fallback we just return the returned arguments.
        return returned_args

    def initialize_args(self, event: Union[Hashable, TEvent], *args) -> Tuple[Any, ...]:
        """ If the event is an instance of the event class, pass it as the first argument."""
        if isinstance(event, self.event_klass):
            return event, *args

        return args

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs):
        if event not in self.listeners:
            return

        args = self.initialize_args(event, *args)

        for listener in self.listeners[event]:
            ret = await listener(*args, **kwargs)
            args = self.update_args(event, args, ret)

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs):
        """
        Skip all async listeners and only emit to synchronous listeners.
        """

        if event not in self.listeners:
            return

        args = self.initialize_args(event, *args)

        for listener in self.listeners[event]:
            if listener.is_async:
                continue

            ret = listener.handler(*args, **kwargs)
            args = self.update_args(event, args, ret)

    def emit_task(self, event: Union[Hashable, TEvent], *args, **kwargs) -> asyncio.Future:
        """Allows for synchronous emitting of events. Useful cross-thread communication."""
        return asyncio.run_coroutine_threadsafe(self.emit(event, *args, **kwargs), self.loop_factory())

    def emit_wrap(self, event: Union[Hashable, TEvent], sync_only=False):
        """
        Returns a curried function that emits the given event with any arguments passed to it.
        
        When sync_only is specified the function will only invoke synchronous listeners. 
        """

        emit_func = self.emit_sync if sync_only else self.emit
        return lambda *args, **kwargs: emit_func(event, *args, **kwargs)

    def on(self, event_type: Hashable, listener: Optional[Callable] = None, priority: int = 0, generic: bool = False):
        if listener is None:
            return lambda lst: self._register_listeners(event_type, lst, priority, generic)

        return self._register_listeners(event_type, listener, priority, generic)

    def _register_listeners(self, event_type: Union[Hashable, TEvent], listener: Callable, priority=0,
                            generic: bool = False) -> Callable:
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

        yield klass
