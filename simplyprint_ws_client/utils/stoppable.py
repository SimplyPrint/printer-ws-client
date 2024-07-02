import asyncio
import multiprocessing
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union, TypeVar, Generic

from .async_task_scope import AsyncTaskScope

TStopEvent = TypeVar("TStopEvent", bound=Union[threading.Event, asyncio.Event, multiprocessing.Condition])
TCondition = TypeVar("TCondition", bound=Union[threading.Condition, asyncio.Condition, multiprocessing.Condition])
TAnyStoppable = Union["Stoppable", TStopEvent]


class StoppableInterface(ABC):
    @abstractmethod
    def is_stopped(self) -> bool:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...


class Stoppable(Generic[TStopEvent, TCondition], StoppableInterface, ABC):
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

    # Implement wait group with a chained condition
    __condition: Optional[TCondition]

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

        if not isinstance(stoppable, (threading.Event, asyncio.Event, multiprocessing.Event)):
            return default

        return stoppable

    @staticmethod
    def _extract_condition(
            nested_stoppable: Optional["SyncStoppable"] = None,
            parent_stoppable: Optional["SyncStoppable"] = None,
            default: Optional[TCondition] = None,
            **kwargs,
    ) -> TCondition:
        stoppable = nested_stoppable or parent_stoppable

        if not stoppable or not isinstance(stoppable, Stoppable):
            return default

        return stoppable.__condition

    @abstractmethod
    def __init__(
            self,
            nested_stoppable: Optional[TAnyStoppable] = None,
            parent_stoppable: Optional[TAnyStoppable] = None,
            condition: Optional[TCondition] = None,
            default_condition: Optional[TCondition] = None,
    ):
        # Only set a condition if it is explicitly passed (and used)
        # for instance, the async stoppable does not use a condition.
        if default_condition:
            self.__condition = self._extract_condition(nested_stoppable, parent_stoppable, default=default_condition)
        else:
            self.__condition = condition

        self.__parent_stop_event = self._extract_stop_event(parent_stoppable)
        self.__stop_event = self._extract_stop_event(nested_stoppable)

    def is_stopped(self):
        if self._parent_stop_event_property is not None:
            return self.__stop_event.is_set() or self.__parent_stop_event.is_set()

        return self.__stop_event.is_set()

    def stop(self):
        self.__stop_event.set()

        if self.__condition:
            with self.__condition:
                self.__condition.notify_all()

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

    @property
    def _condition_property(self):
        return self.__condition


class SyncStoppable(Stoppable[threading.Event, threading.Condition]):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_condition=threading.Condition())
        self._stop_event_property = self._stop_event_property or threading.Event()

    def wait(self, timeout: Optional[float] = None) -> bool:
        with self._condition_property:
            self._condition_property.wait(timeout)
        return self.is_stopped()


class AsyncStoppable(Stoppable[asyncio.Event, asyncio.Condition]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event_property = self._stop_event_property or asyncio.Event()

    async def wait(self, timeout: Optional[float] = None) -> bool:
        with AsyncTaskScope() as task_scope:
            try:
                if self._parent_stop_event_property is not None:
                    await asyncio.wait(
                        map(task_scope.create_task,
                            [
                                self._stop_event_property.wait(),
                                self._parent_stop_event_property.wait()
                            ]),
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED)
                    return self.is_stopped()

                return await asyncio.wait_for(self._stop_event_property.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return self.is_stopped()


class ProcessStoppable(Stoppable[multiprocessing.Event, multiprocessing.Condition]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, default_condition=multiprocessing.Condition())
        self._stop_event_property = self._stop_event_property or multiprocessing.Event()

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self.is_stopped():
            return True

        with self._condition_property:
            self._condition_property.wait(timeout)
        return self.is_stopped()


class StoppableThread(SyncStoppable, threading.Thread, ABC):
    def __init__(self, *args, **kwargs):
        SyncStoppable.__init__(self, *args, **kwargs)
        threading.Thread.__init__(self)

    @abstractmethod
    def run(self):
        ...


class StoppableProcess(ProcessStoppable, multiprocessing.Process, ABC):
    def __init__(self, *args, **kwargs):
        ProcessStoppable.__init__(self, *args, **kwargs)
        multiprocessing.Process.__init__(self)

    @abstractmethod
    def run(self):
        ...
