import json
import time
from typing import Optional
from pympler.tracker import SummaryTracker
from simplyprint_ws.multiplexer import Multiplexer, MultiplexerMode
from tornado.websocket import WebSocketClientConnection
import threading
import asyncio
import logging

from simplyprint_ws.config import get_pending_config
from ..examples.virtual_client import VirtualSuperClient

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    mp = Multiplexer(MultiplexerMode.MULTIPRINTER)

    tracker = SummaryTracker()
    try:
        mpt = threading.Thread(target=mp.start)
        mpt.start()
        printer_threads = []

        for _ in range(1):
            config = get_pending_config()
            client = VirtualSuperClient(config)
            mp.add_client(client)
            printer_threads.append(threading.Thread(target=asyncio.run, args=(client.printer_loop(),)))

        for t in printer_threads: t.start()

    except KeyboardInterrupt:
        mp.stop()
    finally:
        mpt.join()
        for t in printer_threads: t.join()

    tracker.print_diff()
