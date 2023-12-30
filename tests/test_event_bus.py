import asyncio
import unittest
from simplyprint_ws_client.events.client_events import ClientEvent

from simplyprint_ws_client.events.event import Event
from simplyprint_ws_client.events.event_bus import EventBus, EventBusListeners
from simplyprint_ws_client.events.server_events import ServerEvent, ConnectEvent

class CustomEvent(Event):
    def __init__(self, data = None) -> None:
        self.data = data

    @classmethod
    def get_name(cls) -> str:
        return "custom"

class CustomEventBus(EventBus[CustomEvent]):
    ...

class DefaultEventBus(EventBus[Event]):
    ...

class TestEventBus(unittest.IsolatedAsyncioTestCase):
    custom_event_bus: CustomEventBus
    called_test = 0
    called_other = 0
    called_custom = 0
    called_always = 0

    def setUp(self) -> None:
        self.custom_event_bus = CustomEventBus()
        self.custom_event_bus.on("test", self.on_test)
        self.custom_event_bus.on("other", self.on_other)

        self.custom_event_bus.on(CustomEvent, self.on_custom)
        self.custom_event_bus.on(CustomEvent, self.on_always, generic=True)

        self.default_event_bus = DefaultEventBus()
        self.default_event_bus.on(ClientEvent, self.on_client_event, generic=True)
        self.default_event_bus.on(ServerEvent, self.on_server_event, generic=True)
    
    async def on_client_event(self, event: ClientEvent):
        if not isinstance(event, ClientEvent):
            raise Exception("Event is not a ClientEvent")

    async def on_server_event(self, event: ServerEvent):
        if not isinstance(event, ServerEvent):
            raise Exception("Event is not a ServerEvent")

    async def on_test(self, event_type, event: CustomEvent):
        self.called_test += 1

    def on_other(self, event_type, event: CustomEvent):
        self.called_other += 1

    def on_custom(self, event: CustomEvent):
        self.called_custom += 1

    def on_always(self, event: CustomEvent):
        self.called_always += 1

    async def test_custom_event_bus(self):
        self.assertEqual(len(self.custom_event_bus.listeners[CustomEvent]), 2)

        await self.custom_event_bus.emit("test", CustomEvent())
        self.assertEqual(self.called_test, 1)

        await self.custom_event_bus.emit("other", CustomEvent())
        self.assertEqual(self.called_other, 1)

        await self.custom_event_bus.emit("other", CustomEvent())
        await self.custom_event_bus.emit("other", CustomEvent())

        self.assertEqual(self.called_other, 3)

        await self.custom_event_bus.emit(CustomEvent())
        self.assertEqual(self.called_custom, 1)
        await self.custom_event_bus.emit(CustomEvent())
        await self.custom_event_bus.emit(CustomEvent())

        self.assertEqual(self.called_always, 3)
    
    async def test_default_event_bus(self):
        await self.default_event_bus.emit(ClientEvent())
        await self.default_event_bus.emit(ConnectEvent("connected"))
        await self.default_event_bus.emit(CustomEvent())

    def test_event_listener_adding(self):
        event_listeners = EventBusListeners()

        def func1():
            pass

        def func2():
            pass

        event_listeners.add(func1, priority=0)
        event_listeners.add(func2, priority=0)

        self.assertEqual(len(event_listeners), 2)

        event_bus = EventBus()

        event_bus.on(CustomEvent, func1)
        event_bus.on(CustomEvent, func2, generic=True)

        self.assertEqual(len(event_bus.listeners[CustomEvent]), 2)
