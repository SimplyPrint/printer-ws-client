import asyncio
import logging
from abc import ABC
from queue import Queue, Empty
from typing import Union, Hashable, NamedTuple, Optional, Dict, Tuple, Any

from simplyprint_ws_client.helpers.physical_machine import PhysicalMachine
from .emitter import TEvent, Emitter
from .event_bus import EventBus
from ..utils.stoppable import StoppableThread, AsyncStoppable, StoppableInterface


class _EventQueueItem(NamedTuple):
    is_async: bool
    event: Any
    args: Tuple
    kwargs: Dict


_TEventQueueValue = Optional[_EventQueueItem]

# Calculate max queue size based on memory constraints
# Base buffer of unprocessed events is 5000, for every additional 256MB of memory, add 100 to the buffer
_MAX_QUEUE_SIZE = 5000 + ((PhysicalMachine().total_memory() // (256 * 1024 * 1024)) * 100)


class EventBusWorker(Emitter[TEvent], StoppableInterface, ABC):
    event_bus: EventBus[TEvent]
    event_queue: Union[Queue[_TEventQueueValue], asyncio.Queue]

    def __init__(self, event_bus: EventBus[TEvent]) -> None:
        self.event_bus = event_bus

    def _full_warning(self):
        if self.event_queue.full():
            logging.warning(
                f"Event queue worker is full, {self.event_queue.qsize()} events are pending!!! Expect degraded "
                f"performance.")

    def stop(self):
        super().stop()

        # Clear out queue and put a None to signal the end
        try:
            while True:
                self.event_queue.get_nowait()
        except Empty:
            pass

        self.event_queue.put_nowait(None)


class ThreadedEventBusWorker(EventBusWorker[TEvent], StoppableThread):
    def __init__(self, event_bus: EventBus[TEvent], *args, **kwargs):
        EventBusWorker.__init__(self, event_bus)
        StoppableThread.__init__(self, *args, **kwargs)
        self.event_queue = Queue(maxsize=_MAX_QUEUE_SIZE)

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

            try:
                if item.is_async:
                    self.event_bus.emit_task(item.event, *item.args, **item.kwargs)
                else:
                    self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)
            except Exception as e:
                logging.exception(f"Error while processing event {item.event}", exc_info=e)


class AsyncEventBusWorker(EventBusWorker[TEvent], AsyncStoppable):
    def __init__(self, event_bus: EventBus[TEvent], *args, **kwargs):
        EventBusWorker.__init__(self, event_bus)
        AsyncStoppable.__init__(self, *args, **kwargs)
        self.event_queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)

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

            try:
                if item.is_async:
                    await self.event_bus.emit(item.event, *item.args, **item.kwargs)
                else:
                    self.event_bus.emit_sync(item.event, *item.args, **item.kwargs)
            except Exception as e:
                logging.exception(f"Error while processing event {item.event}", exc_info=e)
