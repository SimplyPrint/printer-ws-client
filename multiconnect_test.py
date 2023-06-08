import asyncio
import logging
import threading

from simplyprint_ws_client.config import Config
from simplyprint_ws_client.multiconnection import MultiConnection
from virtual_printer import VirtualPrinter

async def main():
    mp = MultiConnection()
    await mp.connect()

    c = Config()
    p = VirtualPrinter(c.id, c.token, log_level=logging.INFO)
    threading.Thread(target=p.start).start()

    mp.start()
    await mp.add_connection(p)
    await mp.read_from_ws()


if __name__ == "__main__":
    # Run main blocking with asyncio
    asyncio.run(main())

    while True:
        pass
