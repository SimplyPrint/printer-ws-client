import threading
import asyncio

from asyncio import AbstractEventLoop
from typing import Coroutine
from concurrent.futures import Future

class AsyncLoop:
    def __init__(self):
        self.thread = threading.Thread(
            target=self._run_thread, 
            daemon=True,
        )

        self.aioloop: AbstractEventLoop = asyncio.get_event_loop()
        asyncio.set_event_loop(self.aioloop)

    def _run_thread(self) -> None:
        self.aioloop.run_forever()

    def start(self) -> None:
        if self.thread.is_alive():
            return
        self.thread.start()

    def stop(self) -> None:
        self.aioloop.stop()
        self.thread.join() 

    # spawn a future on the async io thread
    # 
    # NOTE: this might not be optimal
    def spawn(self, coro: Coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.aioloop)
