import asyncio
import functools
from abc import ABC, abstractmethod
from typing import Callable, Tuple, Dict

from .event_bus_listeners import EventBusListener, ListenerLifetimeForever
from .event_bus_predicate_bucket import EventBusPredicateBucket
from ..utils.event_loop_provider import EventLoopProvider
from ..utils.predicate import Predicate


class EventBusMiddleware(EventBusListener, ABC):
    """An event bus middleware is a synchronous listener that is always called before any other listener."""

    def __init__(self, *args, **kwargs):
        super().__init__(lifetime=ListenerLifetimeForever(**{}), priority=0, handler=self.handle)

        assert not self.is_async, 'EventBusMiddleware must be synchronous.'

    @abstractmethod
    def handle(self, *args, **kwargs):
        raise NotImplementedError()


class EventBusPredicateResponseMiddleware(EventBusMiddleware, EventLoopProvider):
    """Allow for smart waiting of responses based on predicates that are evaluated on the event arguments."""

    predicate_bucket: EventBusPredicateBucket[Callable]

    def __init__(self, *args, **kwargs):
        EventLoopProvider.__init__(self, *args, **kwargs)
        EventBusMiddleware.__init__(self, *args, **kwargs)

        self.predicate_bucket = EventBusPredicateBucket()

    def create_response(self, *predicates: Predicate) -> asyncio.Future:
        loop = self.event_loop
        future = loop.create_future()

        resource_id = None

        def on_response(*args, **kwargs):
            nonlocal resource_id

            if future.done():
                return

            loop.call_soon(future.set_result, (args, kwargs))

        resource_id = self.predicate_bucket.add(on_response, *predicates)
        future.add_done_callback(lambda _: self.predicate_bucket.remove_resource_id(resource_id))

        return future

    async def wait_for_response(self, *predicates: Predicate, timeout: float = None) -> Tuple[Tuple, Dict]:
        future = self.create_response(*predicates)
        return await asyncio.wait_for(future, timeout=timeout)

    async def create_response_queue(self, *predicates: Predicate, maxsize=0) -> Tuple[asyncio.Queue, Callable]:
        loop = self.event_loop

        queue = asyncio.Queue(maxsize=maxsize)

        def on_response(*args, **kwargs):
            loop.call_soon(queue.put_nowait, (args, kwargs))

        resource_id = self.predicate_bucket.add(on_response, *predicates)

        return queue, functools.partial(self.predicate_bucket.remove_resource_id, resource_id)

    def handle(self, *args, **kwargs):
        for resource_id in self.predicate_bucket.evaluate(*args, **kwargs):
            callback = self.predicate_bucket.resources.get(resource_id)

            # TODO: Log when a resource id in the tree exists without an attached resource.
            if not callback:
                continue

            callback(*args, **kwargs)
