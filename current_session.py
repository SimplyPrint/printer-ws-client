from simplyprint_ws_client.config.json import JsonConfigManager
from simplyprint_ws_client.config.memory import MemoryConfigManager
from simplyprint_ws_client.connection import *
import asyncio
import logging
from simplyprint_ws_client.examples.virtual.virtual_client import VirtualClient
from simplyprint_ws_client.instance.multi_printer import MultiPrinter
from simplyprint_ws_client.instance.single_printer import SinglePrinter

logging.basicConfig(level=logging.DEBUG)

cm = JsonConfigManager()
cm.load()
c = cm.get_all()[0]

client = VirtualClient(c) 

async def main(): 
    loop = asyncio.get_event_loop()
    i = MultiPrinter(loop, cm, allow_setup=True)
    await i.register_client(client)
    await i.connection.connect()
    await i.run()
    await asyncio.sleep(1)
    print("say what boi")

asyncio.run(main())