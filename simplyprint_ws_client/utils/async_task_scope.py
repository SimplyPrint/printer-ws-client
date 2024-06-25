import asyncio
import contextlib


class AsyncTaskScope:
    """Automatically cleanup tasks when exiting a context, to prevent leaks."""

    loop: asyncio.AbstractEventLoop
    tasks: set[asyncio.Task]

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.tasks = set()

    def create_task(self, *args, **kwargs):
        # SAFETY: By design this is safe as long as the API agreements of this class is upheld.
        task = self.loop.create_task(*args, **kwargs)
        self.tasks.add(task)
        return task

    @contextlib.contextmanager
    def scope(self, *args, **kwargs):
        task = self.create_task(*args, **kwargs)

        try:
            yield task
        finally:
            self.tasks.remove(task)
            task.cancel()

    def cancel_all(self):
        for task in self.tasks:
            task.cancel()

        self.tasks.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cancel_all()
        return False
