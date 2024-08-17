import asyncio
import heapq
import inspect
from enum import Enum
from typing import (Callable, List,
                    Union, Tuple, NamedTuple, Optional, get_args, Iterable, Iterator)

try:
    from typing import Unpack, NotRequired, TypedDict
except ImportError:
    from typing_extensions import Unpack, NotRequired, TypedDict

from .emitter import Emitter


class ListenerUniqueness(Enum):
    """ The level of uniqueness for an event listener

    Could also be called a replacement strategy.
    """
    NONE = 0
    PRIORITY = 1
    EXCLUSIVE = 2
    EXCLUSIVE_WITH_ERROR = 3


class ListenerLifetime(NamedTuple):
    """Implement listener lifetime options as a tagged-union
    to support value based lifetimes such as max-calls in the future.
    """
    ...


class ListenerLifetimeOnce(ListenerLifetime):
    """An event listener that is removed after being called once."""
    ...


class ListenerLifetimeForever(ListenerLifetime):
    """A normal event listener that is never removed."""
    ...


class EventBusListenerOptions(TypedDict):
    lifetime: NotRequired[ListenerLifetime]
    priority: NotRequired[int]
    unique: NotRequired[ListenerUniqueness]


class EventBusListenersOptions(EventBusListenerOptions, TypedDict):
    generic: NotRequired[bool]


class EventBusListener:
    __slots__ = ('lifetime', 'priority', 'handler', 'is_async', 'forward_emitter')

    lifetime: ListenerLifetime
    priority: int
    handler: Callable
    is_async: bool
    forward_emitter: Optional[str]

    async def __call__(self, *args, **kwargs):
        if not self.is_async:
            return self.handler(*args, **kwargs)

        return await self.handler(*args, **kwargs)

    def __init__(self, lifetime: ListenerLifetime, priority: int, handler: Callable) -> None:
        self.lifetime = lifetime
        self.priority = priority
        self.handler = handler
        self.is_async = asyncio.iscoroutinefunction(handler)
        self.forward_emitter = None

        # If function takes a named argument with the type Emitter, store that kwarg name.
        signature = inspect.signature(handler)

        for parameter in signature.parameters.values():
            annotation = parameter.annotation

            # Check if the annotation is a type or a type hint. And whether it is a subclass of Emitter.
            if not any(
                    issubclass(cls, Emitter) for cls in get_args(annotation) + (annotation,) if isinstance(cls, type)):
                continue

            self.forward_emitter = parameter.name
            break

    def __lt__(self, other: 'EventBusListener') -> bool:
        return self.priority < other.priority

    def __eq__(self, other: Union['EventBusListener', Callable]) -> bool:
        if isinstance(other, EventBusListener):
            return self.handler == other.handler

        return self.handler == other

    def __hash__(self) -> int:
        return hash(self.handler)

    def __repr__(self):
        return f"EventListener(handler={self.handler.__name__}, priority={self.priority})"


class EventBusListeners(Iterable[EventBusListener]):
    __slots__ = ('listeners',)

    listeners: List[Tuple[int, EventBusListener]]

    def __init__(self) -> None:
        self.listeners = []

    def add(self, listener: Callable, **kwargs: Unpack[EventBusListenerOptions]) -> None:
        unique = kwargs.get('unique', ListenerUniqueness.NONE)
        priority = kwargs.get('priority', 0)
        lifetime = kwargs.get('lifetime', ListenerLifetimeForever(**{}))

        # Handle replacement strategy.
        if unique == ListenerUniqueness.EXCLUSIVE_WITH_ERROR and len(self.listeners) > 0:
            raise ValueError("Exclusive listener already registered, raising an error.")

        if unique == ListenerUniqueness.EXCLUSIVE:
            self.listeners = []
        elif unique == ListenerUniqueness.PRIORITY:
            # Remove all listeners with the same priority
            self.listeners = [(p, l) for p, l in self.listeners if p != priority]

        if self.contains(listener):
            raise ValueError("Listener already registered")

        heapq.heappush(self.listeners, (priority,
                                        EventBusListener(lifetime, priority, listener)))

    def remove(self, listener: Callable) -> None:
        for i, (_, reg_listener) in reversed(list(enumerate(self.listeners))):
            if reg_listener == listener:
                self.listeners.pop(i)
                break

    def contains(self, listener: Callable) -> bool:
        for _, reg_listener in self.listeners:
            if reg_listener == listener:
                return True

        return False

    def __iter__(self) -> Iterator[EventBusListener]:
        """Iterate over listeners in priority order."""
        for _, listener in heapq.nlargest(len(self.listeners), list(self.listeners)):
            # Only allow once shot listener to be consumed once.
            if isinstance(listener.lifetime, ListenerLifetimeOnce):
                self.remove(listener)

            yield listener

    def __len__(self) -> int:
        return len(self.listeners)
