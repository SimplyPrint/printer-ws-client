import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union

TEvent = Union[threading.Event, asyncio.Event]


class Stoppable(ABC):
    """A Stoppable class represents an object that has
    some never ending logic that needs to be able to
    terminate for cleanup.

    This paradigm implements "pausing" or "restarting"
    as always stopping entirely first before creating
    a new instance.

    """
    _stop_event: TEvent

    @abstractmethod
    def __init__(self, stop_chained: Optional[TEvent] = None):
        ...

    def stop(self):
        self._stop_event.set()

    def clear(self):
        self._stop_event.clear()

    def is_stopped(self):
        return self._stop_event.is_set()

    @property
    def stop_event(self):
        return self._stop_event

    @abstractmethod
    def wait(self, timeout: Optional[float] = None) -> bool:
        ...


class SyncStoppable(Stoppable):
    def __init__(self, stop_chained: Optional[threading.Event] = None):
        self._stop_event = stop_chained or threading.Event()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._stop_event.wait(timeout)


class AsyncStoppable(Stoppable):
    def __init__(self, stop_chained: Optional[asyncio.Event] = None):
        self._stop_event = stop_chained or asyncio.Event()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        return await self._stop_event.wait(timeout)


class StoppableThread(ABC, threading.Thread, SyncStoppable):
    @abstractmethod
    def run(self):
        ...
