from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import TypeVar, Generic, Union

# Typically JPEG bytes.
FrameT = TypeVar('FrameT', bound=Union[bytes, bytearray, memoryview])
TCameraConfig = TypeVar('TCameraConfig')
TCameraState = TypeVar('TCameraState')


class CameraProtocolException(Exception):
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


class BaseCameraProtocol(ABC, Generic[TCameraConfig, TCameraState]):
    @staticmethod
    @abstractmethod
    def polling_mode() -> CameraProtocolPollingMode:
        """Camera polling mode"""
        ...

    @staticmethod
    @abstractmethod
    def test(config: TCameraConfig) -> bool:
        """Is the configuration valid?"""
        ...

    @staticmethod
    @abstractmethod
    def connect(config: TCameraConfig) -> TCameraState:
        """Initialize the connection state"""
        ...

    @staticmethod
    @abstractmethod
    def disconnect(state: TCameraState):
        """Cleanup camera state"""
        ...

    @staticmethod
    @abstractmethod
    def read(state: TCameraState) -> FrameT:
        """Block until an entire frame has been received"""
        ...
