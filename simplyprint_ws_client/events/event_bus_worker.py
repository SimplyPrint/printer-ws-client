import asyncio
import logging
from abc import ABC, abstractmethod
from queue import Queue, Empty
from typing import Union, Hashable, NamedTuple, Optional, Dict, Tuple, Any, Coroutine

from .emitter import TEvent, Emitter
from .event_bus import EventBus
from ..shared.utils.stoppable import StoppableThread, AsyncStoppable, StoppableInterface


class _EventQueueItem(NamedTuple):
    is_async: bool
    event: Any
    args: Tuple
    kwargs: Dict


_TEventQueueValue = Optional[_EventQueueItem]

_MAX_QUEUE_SIZE = 10000


class EventBusWorker(Emitter[TEvent], StoppableInterface, ABC):
    event_bus: EventBus[TEvent]
    event_queue: Union[Queue[_TEventQueueValue], asyncio.Queue]
    logger: logging.Logger = logging.getLogger(__name__)
    maxsize: int

    def __init__(self, event_bus: EventBus[TEvent], *args, maxsize=_MAX_QUEUE_SIZE,
                 logger: Optional[logging.Logger] = None, **kwargs) -> None:
        self.event_bus = event_bus
        self.logger = logger or self.logger
        self.maxsize = maxsize

    @abstractmethod
    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs) -> Union[None, Coroutine[Any, Any, None]]:
        ...

    @abstractmethod
    def emit(self, event: Union[Hashable, TEvent], *args, **kwargs) -> Union[None, Coroutine[Any, Any, None]]:
        ...

    def _full_warning(self):
        if self.event_queue.full():
            self.logger.warning(
                f"Event queue worker is full, {self.event_queue.qsize()} events are pending!!! Expect degraded "
                f"performance.")

    def stop(self):
        super().stop()

        # Clear out queue and put a None to signal the end
        try:
            while True:
                self.event_queue.get_nowait()
        except (Empty, asyncio.QueueEmpty):
            pass

        self.event_queue.put_nowait(None)


class ThreadedEventBusWorker(EventBusWorker[TEvent], StoppableThread):
    def __init__(self, event_bus: EventBus[TEvent], **kwargs):
        EventBusWorker.__init__(self, event_bus, **kwargs)
        StoppableThread.__init__(self, **kwargs)
        self.event_queue = Queue(maxsize=self.maxsize)

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        if self.is_stopped():
            return

        self._full_warning()

        self.event_queue.put_nowait(_EventQueueItem(True, event, args, kwargs))

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        if self.is_stopped():
            return

        self._full_warning()

        self.event_queue.put(_EventQueueItem(False, event, args, kwargs))

    def run(self):
        while not self.is_stopped():
            item = self.event_queue.get()

            if item is None:
                break

            self.event_queue.task_done()

            try:
                if item.is_async:
                    self.event_bus.emit_task(item.event, *item.args, **item.kwargs)
                else:
                    self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)
            except Exception as e:
                self.logger.error(f"Error while processing event {item.event}", exc_info=e)


class AsyncEventBusWorker(EventBusWorker[TEvent], AsyncStoppable):
    def __init__(self, event_bus: EventBus[TEvent], *args, **kwargs):
        EventBusWorker.__init__(self, event_bus, *args, **kwargs)
        AsyncStoppable.__init__(self, *args, **kwargs)
        self.event_queue = asyncio.Queue(maxsize=self.maxsize)

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        if self.is_stopped():
            return

        self._full_warning()

        await self.event_queue.put(_EventQueueItem(True, event, args, kwargs))

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        if self.is_stopped():
            return

        self._full_warning()

        self.event_queue.put_nowait(_EventQueueItem(False, event, args, kwargs))

    async def run(self):
        while not self.is_stopped():
            item = await self.event_queue.get()

            if item is None:
                break

            self.event_queue.task_done()

            try:
                if item.is_async:
                    await self.event_bus.emit(item.event, *item.args, **item.kwargs)
                else:
                    self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)
            except Exception as e:
                self.logger.error(f"Error while processing event {item.event}", exc_info=e)
