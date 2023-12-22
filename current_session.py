# coding: utf-8
from math import log
from typing import Iterable, Optional, Union
from simplyprint_ws_client.client import Client, DefaultClient
from simplyprint_ws_client.config.config import Config
from simplyprint_ws_client.config.memory import MemoryConfigManager
from simplyprint_ws_client.connection import *
import asyncio
import logging
from simplyprint_ws_client.connection import ConnectionConnectedEvent, ConnectionDisconnectEvent, ConnectionReconnectEvent
from simplyprint_ws_client.events.client_events import ClientEvent, PingEvent
from simplyprint_ws_client.events.demands import DemandEvent
from simplyprint_ws_client.events.server_events import ServerEvent
from simplyprint_ws_client.instance.instance import Instance

logging.basicConfig(level=logging.DEBUG)

class PingPongClient(Client):
    async def tick(self):
        await self.send_event(PingEvent(self.printer))

client = PingPongClient(Config(id=10, token="Whatthefuck")) 
client.printer.connected = True

class TestInstance(Instance[DefaultClient, Config]):
    def add_client(self, client: DefaultClient) -> None:
        ...

    def get_client(self, config: Config) -> DefaultClient | None:
        ...

    def get_clients(self) -> Iterable[DefaultClient]:
        return [  ]

    def has_client(self, client: DefaultClient) -> bool:
        ...

    def remove_client(self, client: DefaultClient) -> None:
        ...

    def should_connect(self) -> bool:
        return True

    async def on_client_event(self, client: DefaultClient, event: ClientEvent):
        await self.connection.send_event(event)

    async def on_event(self, client: DefaultClient, event: ServerEvent | DemandEvent):
        ...

    async def on_connect(self, _: ConnectionConnectedEvent):
        ...

    async def on_reconnect(self, _: ConnectionReconnectEvent):
        ...
    
    async def on_disconnect(self, _: ConnectionDisconnectEvent):
        ...

async def main(): 
    loop = asyncio.get_event_loop()
    i = TestInstance(loop, MemoryConfigManager())
    i.connection.set_url("wss://testws3.simplyprint.io/0.1/p/0/6667b488-d07d-4eed-8f55-8d912d5876e6")
    await i.register_client(client)
    await i.connection.connect()
    await i.run()
    await asyncio.sleep(1)
    print("say what boi")

asyncio.run(main())