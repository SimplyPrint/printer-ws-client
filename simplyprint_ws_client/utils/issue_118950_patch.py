# Implements https://github.com/python/cpython/pull/118960
# Without needing to modify the source code of the library.
# UVLoop also experiences this issue, so we default to asyncio.
# Issue: https://github.com/python/cpython/issues/118950

from asyncio.sslproto import _SSLProtocolTransport, SSLProtocol


def _is_transport_closing(self) -> bool:
    return self._transport is not None and self._transport.is_closing()


SSLProtocol._is_transport_closing = _is_transport_closing


def is_closing(self) -> bool:
    return self._closed or self._ssl_protocol._is_transport_closing()


_SSLProtocolTransport.is_closing = is_closing
