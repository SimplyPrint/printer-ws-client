import asyncio
import unittest

from simplyprint_ws_client.core.ws_protocol.messages import MultiPrinterAddedMsg
from simplyprint_ws_client.events import EventBus
from simplyprint_ws_client.events.event_bus_middleware import EventBusPredicateResponseMiddleware
from simplyprint_ws_client.shared.events.predicate import IsInstance, Eq, Extract
from simplyprint_ws_client.shared.events.property_path import p


class TestEventBus(unittest.IsolatedAsyncioTestCase):
    async def test_simple(self):
        event_bus = EventBus()
        event_bus_response = EventBusPredicateResponseMiddleware(provider=event_bus.event_loop_provider)
        event_bus.middleware.add(event_bus_response)

        future = event_bus_response.create_response(IsInstance(MultiPrinterAddedMsg),
                                                    Extract(p.unique_id) | Eq("something"))
        future.set_result((None, None))

        await future
        await asyncio.sleep(0.0)

        self.assertEqual(len(event_bus_response.predicate_tree.root.predicates), 0)
