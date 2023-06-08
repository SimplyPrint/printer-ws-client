import json
from typing import Optional
from pympler.tracker import SummaryTracker
from simplyprint_ws.multiplexer import Multiplexer, MultiplexerMode
from tornado.websocket import WebSocketClientConnection
import threading
import asyncio
import logging
import time

from simplyprint_ws.client.client import DefaultClient
from simplyprint_ws.events import ClientEvents, ServerEvent
from simplyprint_ws.config import Config, ConfigManager, get_pending_config

global mp
mp: Optional[Multiplexer] = None

if __name__ == "__main__":
    all_configs = ConfigManager().get_all_configs()

    if len(all_configs) > 0:
        config = all_configs[0]
    else:
        config = get_pending_config()

    mp = Multiplexer(MultiplexerMode.SINGLE, config)
    client = DefaultClient(config)
    mp.add_client(config, client)

    tracker = SummaryTracker()
    try:
        logging.basicConfig(level=logging.DEBUG)
        # s = threading.Thread(target=asyncio.run, args=(mp.start(),))
        asyncio.run(mp.start())
        # s.start()
    except KeyboardInterrupt:
        mp.stop()
    finally:
        # s.join()
        pass

    tracker.print_diff()
