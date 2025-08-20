from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import (
    Union,
    Iterator,
    Iterable,
    AsyncIterable,
    AsyncIterator,
    Coroutine,
    ClassVar,
)

from yarl import URL

# Typically JPEG bytes.
FrameT = Union[bytes, bytearray, memoryview]


class CameraProtocolException(Exception): ...


class CameraProtocolConnectionError(CameraProtocolException, ConnectionError):
    """Raise when the connection to the camera fails."""

    ...


class CameraProtocolInvalidState(CameraProtocolException):
    """Raise when the camera state needs to be destroyed and recreated."""

    ...


class CameraProtocolPollingMode(Enum):
    """Camera protocol polling mode"""

    CONTINUOUS = auto()
    """Must keep polling"""

    ON_DEMAND = auto()
    """Snapshot based"""


class BaseCameraProtocol(ABC, Iterable[FrameT], AsyncIterable[FrameT]):
    polling_mode: ClassVar[CameraProtocolPollingMode] = (
        CameraProtocolPollingMode.ON_DEMAND
    )
    """Camera polling mode"""
    is_async: ClassVar[bool] = False
    """Is the camera protocol async?"""

    uri: URL
    """Configuration URI for the camera protocol, and the only input we have access to."""

    def __init__(self, uri: URL, *args, **kwargs):
        _ = args
        _ = kwargs
        self.uri = uri

    @staticmethod
    @abstractmethod
    def test(uri: URL) -> Union[bool, Coroutine[None, None, bool]]:
        """Is the configuration valid for this protocol?"""
        ...

    @abstractmethod
    def read(
        self,
    ) -> Union[Iterator[FrameT], Coroutine[None, None, AsyncIterator[FrameT]]]:
        """Read frames from the camera, blocking."""
        ...

    def __iter__(self):
        return self.read()

    def __aiter__(self):
        return self.read()
