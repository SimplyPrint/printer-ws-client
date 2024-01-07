from typing import TypedDict, Unpack


class TConfig(TypedDict):
    name: str
    id: str
    token: str


class ExtendedConfig:
    cool: bool


def func(*args, **kwargs: Unpack[TConfig]):
    print(kwargs)


