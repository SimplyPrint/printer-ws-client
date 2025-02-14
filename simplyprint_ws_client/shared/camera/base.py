from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TypeVar, Union, Iterator, Iterable, AsyncIterable, AsyncIterator, Coroutine

from yarl import URL

# Typically JPEG bytes.
FrameT = TypeVar('FrameT', bound=Union[bytes, bytearray, memoryview])


class CameraProtocolException(Exception):
    ...


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
    uri: URL

    def __init__(self, uri: URL, *args, **kwargs):
        self.uri = uri

    @staticmethod
    @abstractmethod
    def polling_mode() -> CameraProtocolPollingMode:
        """Camera polling mode"""
        ...

    @staticmethod
    @abstractmethod
    def is_async() -> bool:
        """Is the camera protocol async?"""
        ...

    @staticmethod
    @abstractmethod
    def test(uri: URL) -> Union[bool, Coroutine[None, None, bool]]:
        """Is the configuration valid for this protocol?"""
        ...

    @abstractmethod
    def read(self) -> Union[Iterator[FrameT], Coroutine[None, None, AsyncIterator[FrameT]]]:
        """Read frames from the camera, blocking."""
        ...

    def __iter__(self):
        return self.read()

    def __aiter__(self):
        return self.read()
