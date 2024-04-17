from typing import Self

from state_effect.version import Version


class Value:
    """A reactive value, holds its version and update function."""

    __version: Version

    def __init__(self):
        self.__version = Version()

    @classmethod
    def of(cls, obj: object) -> Self:
        ...
