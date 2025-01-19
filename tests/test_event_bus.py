import asyncio
import unittest
from typing import Optional

from simplyprint_ws_client.events.event import Event
from simplyprint_ws_client.events.event_bus import EventBus, EventBusListeners
from simplyprint_ws_client.events.event_bus_listeners import ListenerUniqueness, ListenerLifetimeForever, \
    ListenerLifetimeOnce


class CustomEvent(Event):
    def __init__(self, data=None) -> None:
        self.data = data

    @classmethod
    def get_name(cls) -> str:
        return "custom"


class CustomEventBus(EventBus[CustomEvent]):
    ...


class DefaultEventBus(EventBus[Event]):
    ...


class ClientEvent(Event):
    ...


class ServerEvent(Event):
    ...


class ConnectEvent(Event):
    def __init__(self, status: str) -> None:
        super().__init__()
        self.status = status


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

    @staticmethod
    async def on_client_event(event: ClientEvent):
        if not isinstance(event, ClientEvent):
            raise Exception("Event is not a ClientEvent")

    @staticmethod
    async def on_server_event(event: ServerEvent):
        if not isinstance(event, ServerEvent):
            raise Exception("Event is not a ServerEvent")

    async def on_test(self, event: CustomEvent):
        self.called_test += 1

    def on_other(self, event: CustomEvent):
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

    async def test_chained_event_bus(self):
        called_func1 = 0
        called_func2 = 0

        def func1(dispatcher: Optional[EventBus] = None):
            nonlocal called_func1
            called_func1 += 1

            dispatcher.emit_sync("func2")

        def func2():
            nonlocal called_func2
            called_func2 += 1

        event_bus = EventBus()
        event_bus.on("func1", func1)
        event_bus.on("func2", func2)

        await event_bus.emit("func1")

        self.assertEqual(called_func1, 1)
        self.assertEqual(called_func2, 1)

    async def test_one_shot_listener(self):
        event_bus = EventBus()
        called = 0

        def func1():
            nonlocal called
            called += 1

        event_bus.on("test", func1, lifetime=ListenerLifetimeOnce(**{}))

        await event_bus.emit("test")

        self.assertEqual(called, 1)

        await event_bus.emit("test")

        self.assertEqual(called, 1)

        self.assertEqual(len(event_bus.listeners["test"]), 0)

    async def test_one_shot_listener_ret(self):
        event_bus = EventBus()
        loop = event_bus.event_loop_provider.event_loop

        async def expensive_task():
            await asyncio.sleep(0.0)
            return 1337

        async def func1(f: asyncio.Future):
            task = loop.create_task(expensive_task())
            task.add_done_callback(lambda _: f.set_result(task.result()))

        event_bus.on("test", func1, lifetime=ListenerLifetimeOnce(**{}))

        fut = loop.create_future()

        await event_bus.emit("test", fut)

        result = await fut

        self.assertEqual(result, 1337)

    def test_event_listener_adding(self):
        event_listeners = EventBusListeners()

        def func1():
            pass

        def func2():
            pass

        event_listeners.add(func1, lifetime=ListenerLifetimeForever(**{}), priority=0, unique=ListenerUniqueness.NONE)
        event_listeners.add(func2, lifetime=ListenerLifetimeForever(**{}), priority=0, unique=ListenerUniqueness.NONE)

        self.assertEqual(len(event_listeners), 2)

        event_bus = EventBus()

        event_bus.on(CustomEvent, func1)
        event_bus.on(CustomEvent, func2, generic=True)

        self.assertEqual(len(event_bus.listeners[CustomEvent]), 2)
