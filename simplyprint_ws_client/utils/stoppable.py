import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union

TStopEvent = Union[threading.Event, asyncio.Event]


class Stoppable(ABC):
    """A Stoppable class represents an object that has
    some never ending logic that needs to be able to
    terminate for cleanup.

    This paradigm implements "pausing" or "restarting"
    as always stopping entirely first before creating
    a new instance.

    """
    __stop_event: TStopEvent

    @abstractmethod
    def __init__(self, _: Optional[TStopEvent] = None):
        ...

    def stop(self):
        self.__stop_event.set()

    def clear(self):
        self.__stop_event.clear()

    def is_stopped(self):
        return self.__stop_event.is_set()

    @property
    def stop_event(self):
        return self.__stop_event

    @abstractmethod
    def wait(self, timeout: Optional[float] = None) -> bool:
        ...


class SyncStoppable(Stoppable):
    def __init__(self, stop_event: Optional[threading.Event] = None):
        self.__stop_event = stop_event or threading.Event()

    def wait(self, timeout: Optional[float] = None) -> bool:
        return self.__stop_event.wait(timeout)


class AsyncStoppable(Stoppable):
    def __init__(self, stop_event: Optional[asyncio.Event] = None):
        self.__stop_event = stop_event or asyncio.Event()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        return await self.__stop_event.wait(timeout)


class StoppableThread(ABC, threading.Thread, SyncStoppable):
    @abstractmethod
    def run(self):
        ...
