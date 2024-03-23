import asyncio
import heapq
from enum import Enum
from typing import (Callable, Generator, List,
                    Union, Tuple)


class ListenerUniqueness(Enum):
    """ The level of uniqueness for an event listener

    Could also be called a replacement strategy.
    """
    NONE = 0
    PRIORITY = 1
    EXCLUSIVE = 2


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

    def add(self, listener: Callable, priority: int, unique: ListenerUniqueness) -> None:
        # Handle replacement strategy.
        if unique == ListenerUniqueness.EXCLUSIVE:
            self.listeners = []
        elif unique == ListenerUniqueness.PRIORITY:
            # Remove all listeners with the same priority
            self.listeners = [(p, l) for p, l in self.listeners if p != priority]

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
        """Iterate over listeners in priority order."""
        for _, listener in heapq.nlargest(len(self.listeners), self.listeners):
            yield listener

    def __len__(self) -> int:
        return len(self.listeners)
