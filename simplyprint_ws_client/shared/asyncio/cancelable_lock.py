import asyncio
import collections
from typing import Optional


class CancelableLock(asyncio.Lock):
    _waiters: Optional[collections.deque]

    def __len__(self) -> int:
        """Return the number of waiters in the queue."""
        if self._waiters is None:
            return 0

        return len(self._waiters)

    def cancel(self):
        if not self._waiters:
            return

        for waiter in self._waiters:
            if not asyncio.isfuture(waiter) or waiter.done():
                continue

            waiter.cancel("Lock was canceled")


# TODO: move this into a test module.
if __name__ == "__main__":
    lock = CancelableLock()


    async def npc(i):
        await asyncio.sleep(0.1)
        print(f"npc {i} is trying to get lock")

        try:
            async with lock:
                print(f"npc {i} got lock")
                await asyncio.sleep(5)
                print(f"npc {i} is done")
        except asyncio.CancelledError:
            print(f"npc {i} was canceled")


    async def sigma():
        async with lock:
            print("sigma got lock")
            await asyncio.sleep(2)
            print("done now canceling")
            lock.cancel()
            print("sigma done")


    async def main():
        await asyncio.gather(*(npc(i) for i in range(10)), sigma())


    asyncio.run(main())
