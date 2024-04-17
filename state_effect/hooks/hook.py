"""Hook into any state objects given by the user."""

from abc import ABC, abstractmethod

from state_effect.property_path import PropertyPath
from state_effect.value import Value


class Hook(ABC):
    @staticmethod
    @abstractmethod
    def is_object(obj: object) -> bool:
        ...

    @staticmethod
    @abstractmethod
    def load_value(val: Value, obj: object, parent=PropertyPath()):
        ...


class B:
    b: int


class A:
    a: int
    b: B
