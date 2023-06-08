import threading
import asyncio

from asyncio import AbstractEventLoop
from types import FunctionType
from typing import Coroutine, Optional
from concurrent.futures import Future

class AsyncLoop:
    """
    A wrapper around the asyncio event loop that runs in a separate thread.
    """
    def __init__(self):
        self.thread = threading.Thread(
            target=self._run_thread, 
            daemon=True,
        )

        self.aioloop: AbstractEventLoop = asyncio.get_event_loop()

    def _run_thread(self) -> None:
        self.aioloop.run_forever()

    def start(self) -> None:
        if self.thread.is_alive():
            return
        self.thread.start()

    def is_running(self) -> bool:
        return self.thread.is_alive() and self.aioloop.is_running()

    def stop(self) -> None:
        self.aioloop.stop()
        self.thread.join() 

    # spawn a future on the async io thread
    # 
    # NOTE: this might not be optimal
    def spawn(self, coro: Coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.aioloop)
    
class AsyncThread:
    """
    Run a async loop in a seperate thread (with support for multiple coroutines)
    """
    thread: threading.Thread
    loop: Optional[AbstractEventLoop]

    def __init__(self, func: Coroutine):
        self.thread = threading.Thread(
            target=self._run_thread,
            daemon=True,
            args=(func,)
        )

    def _run_thread(self, func: Coroutine) -> None:        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(func)

    def start(self) -> None:
        if self.thread.is_alive():
            return
        self.thread.start()

    def is_running(self) -> bool:
        return self.thread.is_alive() and self.loop.is_running()
    
    def stop(self) -> None:
        self.loop.stop()
        self.thread.join()

    def spawn(self, coro: Coroutine) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)