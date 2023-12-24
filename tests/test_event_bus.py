import asyncio
import unittest

from simplyprint_ws_client.events.event import Event
from simplyprint_ws_client.events.event_bus import EventBus

class CustomEvent(Event):
    def __init__(self, data = None) -> None:
        self.data = data

    @classmethod
    def get_name(cls) -> str:
        return "custom"

class CustomEventBus(EventBus[CustomEvent]):
    ...

class TestEventBus(unittest.IsolatedAsyncioTestCase):
    event_bus: CustomEventBus
    called_test = 0
    called_other = 0
    called_custom = 0
    called_always = 0

    def setUp(self) -> None:
        self.event_bus = CustomEventBus()
        self.event_bus.on("test", self.on_test)
        self.event_bus.on("other", self.on_other)
        self.event_bus.on(CustomEvent, self.on_custom)
        self.event_bus.on_generic(CustomEvent, self.on_always)

    async def on_test(self, event: CustomEvent):
        self.called_test += 1

    def on_other(self, event: CustomEvent):
        self.called_other += 1

    def on_custom(self, event: CustomEvent):
        self.called_custom += 1

    def on_always(self, event: CustomEvent):
        self.called_always += 1

    async def test_event_bus(self):
        await self.event_bus.emit("test", CustomEvent())
        self.assertEqual(self.called_test, 1)

        await self.event_bus.emit("other", CustomEvent())
        self.assertEqual(self.called_other, 1)

        await self.event_bus.emit("other", CustomEvent())
        await self.event_bus.emit("other", CustomEvent())

        self.assertEqual(self.called_other, 3)

        await self.event_bus.emit(CustomEvent())
        self.assertEqual(self.called_custom, 1)
        await self.event_bus.emit(CustomEvent())
        await self.event_bus.emit(CustomEvent())

        self.assertEqual(self.called_always, 3)
        