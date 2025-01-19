"""Polyfills for python compatibility."""
import sys

# Provide asyncio.timeout for Python 3.10 and below.
if sys.version_info < (3, 11):
    import asyncio  # noqa
    from async_timeout import timeout  # noqa

    asyncio.timeout = timeout  # noqa

# Implements https://github.com/python/cpython/pull/118960
# Without needing to modify the source code of the library.
# UVLoop also experiences this issue, so we default to asyncio.
# Issue: https://github.com/python/cpython/issues/118950
# This is fixed in 3.12.8+, 3.13.1+, and all 3.14+ versions.
if sys.version_info < (3, 12, 8) or (sys.version_info.micro == 13 and sys.version_info.minor < 1):
    from asyncio.sslproto import _SSLProtocolTransport, SSLProtocol


    def _is_transport_closing(self) -> bool:
        return self._transport is not None and self._transport.is_closing()


    SSLProtocol._is_transport_closing = _is_transport_closing


    def is_closing(self) -> bool:
        return self._closed or self._ssl_protocol._is_transport_closing()


    _SSLProtocolTransport.is_closing = is_closing

# Provide StrEnum and IntEnum for Python 3.9 and below.
if sys.version_info < (3, 11):
    import enum  # noqa

    if not hasattr(enum, "StrEnum"):  # noqa
        from strenum import StrEnum  # noqa

        enum.StrEnum = StrEnum  # noqa
