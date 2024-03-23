import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union, TypeVar, Generic

TStopEvent = TypeVar("TStopEvent", bound=Union[threading.Event, asyncio.Event])
TAnyStoppable = Union["Stoppable", TStopEvent]


class Stoppable(Generic[TStopEvent], ABC):
    """A Stoppable class represents an object that has
    some never ending logic that needs to be able to
    terminate for cleanup.

    This paradigm implements "pausing" or "restarting"
    as always stopping entirely first before creating
    a new instance.

    Also has the concept of a parent stop event,
    when the child is stopped, the parent is not stopped.

    But when the parent is stopped, the child is stopped.

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

        if isinstance(stoppable, Stoppable):
            return stoppable._stop_event_property

        if not isinstance(stoppable, (threading.Event, asyncio.Event)):
            return default

        return stoppable

    @abstractmethod
    def __init__(self, stoppable: Optional[TAnyStoppable] = None):
        self.__parent_stop_event = self._extract_stop_event(stoppable)

    def is_stopped(self):
        return self.__stop_event.is_set() or (self.__parent_stop_event and self.__parent_stop_event.is_set())

    def stop(self):
        self.__stop_event.set()

    def clear(self):
        self.__stop_event.clear()

    @abstractmethod
    def wait(self, timeout: Optional[float] = None) -> bool:
        ...

    @property
    def _stop_event_property(self):
        return self.__stop_event

    @_stop_event_property.setter
    def _stop_event_property(self, event: TStopEvent):
        self.__stop_event = event

    @property
    def _parent_stop_event_property(self):
        return self.__parent_stop_event


class SyncStoppable(Stoppable[threading.Event]):
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
        self._stop_event_property = threading.Event()

    def stop(self):
        super().stop()

        with self.__condition:
            self.__condition.notify_all()

    def wait(self, timeout: Optional[float] = None) -> bool:
        with self.__condition:
            self.__condition.wait(timeout)
        return self.is_stopped()


class AsyncStoppable(Stoppable[asyncio.Event]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event_property = asyncio.Event()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        try:
            if self._parent_stop_event_property is not None:
                await asyncio.wait(
                    map(asyncio.create_task, [
                        self._stop_event_property.wait(),
                        self._parent_stop_event_property.wait()
                    ]),
                    timeout=timeout,
                    return_when=asyncio.FIRST_COMPLETED)
                return self.is_stopped()

            return await asyncio.wait_for(self._stop_event_property.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return self.is_stopped()


class StoppableThread(SyncStoppable, threading.Thread, ABC):
    def __init__(self, *args, **kwargs):
        SyncStoppable.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)

    @abstractmethod
    def run(self):
        ...
