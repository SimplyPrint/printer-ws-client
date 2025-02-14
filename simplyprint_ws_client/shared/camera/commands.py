from typing import Union, NamedTuple, Optional

from .base import FrameT, BaseCameraProtocol


class CreateCamera(NamedTuple):
    id: int
    protocol: BaseCameraProtocol
    pause_timeout: Optional[int] = None


class PollCamera(NamedTuple):
    id: int


class StartCamera(NamedTuple):
    id: int


class StopCamera(NamedTuple):
    id: int


class DeleteCamera(NamedTuple):
    id: int


Request = Union[
    CreateCamera,
    PollCamera,
    StartCamera,
    StopCamera,
    DeleteCamera,
]


class ReceivedFrame(NamedTuple):
    id: int
    time: float
    data: Optional[FrameT]


Response = Union[
    ReceivedFrame
]
