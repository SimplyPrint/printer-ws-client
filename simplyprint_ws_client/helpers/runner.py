try:
    """ Prefer faster event loop implementation. """
    from uvloop import run as async_run
except ImportError:
    from asyncio import run as async_run


class Runner:
    """ Wrapper around uvloop/asyncio implementations for running the main event loop. """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def run(*args, **kwargs) -> None:
        return async_run(*args, **kwargs)
