from typing import Type, Any, Union, NamedTuple

from .base import BaseCameraProtocol, TCameraConfig, FrameT


class CreateCamera(NamedTuple):
    protocol: Type[BaseCameraProtocol]
    config: TCameraConfig


class ConfigureCamera(NamedTuple):
    config: Any


class PollCamera(NamedTuple):
    ...


class StartCamera(NamedTuple):
    ...


class StopCamera(NamedTuple):
    ...


class DeleteCamera(NamedTuple):
    ...


Request = Union[
    CreateCamera,
    ConfigureCamera,
    PollCamera,
    StartCamera,
    StopCamera,
    DeleteCamera,
]


class ReceivedFrame(NamedTuple):
    ts: float
    data: FrameT


Response = Union[
    ReceivedFrame,
    ...
]
