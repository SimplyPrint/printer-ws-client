"""Polyfill for python compatibility."""
import sys

if sys.version_info < (3, 11):
    import asyncio
    from async_timeout import timeout

    asyncio.timeout = timeout
