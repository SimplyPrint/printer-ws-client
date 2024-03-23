import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union

TStopEvent = Union[threading.Event, asyncio.Event]
TAnyStoppable = Union["Stoppable", TStopEvent]


class Stoppable(ABC):
    """A Stoppable class represents an object that has
    some never ending logic that needs to be able to
    terminate for cleanup.

    This paradigm implements "pausing" or "restarting"
    as always stopping entirely first before creating
    a new instance.

    """

    __parent_stop_event: Optional[TStopEvent]
    __stop_event: TStopEvent

    @classmethod
    def _extract_stop_event(
            cls,
            stoppable: Optional[TAnyStoppable] = None,
            default: Optional[TStopEvent] = None) -> Optional[TStopEvent]:
        if not stoppable:
            return default

        if isinstance(stoppable, cls):
            return stoppable._stop_event

        return stoppable

    @abstractmethod
    def __init__(self, stoppable: Optional[TAnyStoppable] = None):
        self.__parent_stop_event = self._extract_stop_event(stoppable)

    def stop(self):
        self.__stop_event.set()

    def clear(self):
        self.__stop_event.clear()

    def is_stopped(self):
        return self.__stop_event.is_set() or (self.__parent_stop_event and self.__parent_stop_event.is_set())

    @property
    def _stop_event(self):
        return self.__stop_event

    @_stop_event.setter
    def _stop_event(self, event: TStopEvent):
        self.__stop_event = event

    @property
    def _parent_stop_event(self):
        return self.__parent_stop_event

    @abstractmethod
    def wait(self, timeout: Optional[float] = None) -> bool:
        ...


class SyncStoppable(Stoppable):
    # Implement wait group with a chained condition
    __condition: threading.Condition

    @staticmethod
    def _extract_condition(
            stoppable: Optional["SyncStoppable"] = None,
            default: Optional[threading.Condition] = None) -> threading.Condition:
        if not stoppable or not isinstance(stoppable, SyncStoppable):
            return default or threading.Condition()

        return stoppable.__condition

    def __init__(self, *args, condition: Optional[threading.Condition] = None, **kwargs):
        super().__init__(*args, **kwargs)

        self.__condition = SyncStoppable._extract_condition(**kwargs, default=condition)
        self._stop_event = threading.Event()

    def stop(self):
        super().stop()

        with self.__condition:
            self.__condition.notify_all()

    def wait(self, timeout: Optional[float] = None) -> bool:
        with self.__condition:
            self.__condition.wait(timeout)
        return self.is_stopped()


class AsyncStoppable(Stoppable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = asyncio.Event()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        if self.__parent_stop_event is not None:
            await asyncio.wait([self._stop_event.wait(timeout), self._parent_stop_event.wait(timeout)],
                               return_when=asyncio.FIRST_COMPLETED)
            return self.is_stopped()

        return await self._stop_event.wait(timeout)


class StoppableThread(SyncStoppable, threading.Thread, ABC):
    def __init__(self, *args, **kwargs):
        SyncStoppable.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)

    @abstractmethod
    def run(self):
        ...
