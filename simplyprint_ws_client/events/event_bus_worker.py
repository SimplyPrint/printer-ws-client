import asyncio
from abc import ABC
from queue import Queue
from typing import Generic, Union, Hashable, NamedTuple, Optional, Dict, Tuple, Any

from .event_bus import EventBus, Emitable, TEvent
from ..utils.stoppable import StoppableThread, AsyncStoppable, StoppableInterface


class _EventQueueItem(NamedTuple):
    is_async: bool
    event: Any
    args: Tuple
    kwargs: Dict


_TEventQueueValue = Optional[_EventQueueItem]


class EventBusWorker(Generic[TEvent], StoppableInterface, Emitable, ABC):
    event_bus: EventBus[TEvent]
    event_queue: Union[Queue[_TEventQueueValue], asyncio.Queue[_TEventQueueValue]]

    def __init__(self, event_bus: EventBus[TEvent]) -> None:
        self.event_bus = event_bus

    async def emit(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        self.event_queue.put_nowait(_EventQueueItem(True, event, args, kwargs))

    def emit_sync(self, event: Union[Hashable, TEvent], *args, **kwargs) -> None:
        self.event_queue.put_nowait(_EventQueueItem(False, event, args, kwargs))

    def stop(self):
        super().stop()
        self.event_queue.put_nowait(None)


class ThreadedEventBusWorker(EventBusWorker[TEvent], StoppableThread):
    def __init__(self, event_bus: EventBus[TEvent], *args, **kwargs):
        EventBusWorker.__init__(self, event_bus)
        StoppableThread.__init__(self, *args, **kwargs)
        self.event_queue = Queue()

    def run(self):
        while not self.is_stopped():
            item = self.event_queue.get()

            if item is None:
                break

            if item.is_async:
                self.event_bus.emit_task(item.event, *item.args, **item.kwargs)
            else:
                self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)


class AsyncEventBusWorker(EventBusWorker[TEvent], AsyncStoppable):
    def __init__(self, event_bus: EventBus[TEvent], *args, **kwargs):
        EventBusWorker.__init__(self, event_bus)
        AsyncStoppable.__init__(self, *args, **kwargs)
        self.event_queue = asyncio.Queue()

    async def run(self):
        while not self.is_stopped():
            item = await self.event_queue.get()

            if item is None:
                break

            if item.is_async:
                await self.event_bus.emit(item.event, *item.args, **item.kwargs)
            else:
                self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)
