from dataclasses import dataclass, is_dataclass

from state_effect.hooks.hook import Hook
from state_effect.property_path import PropertyPath
from state_effect.version import Version


class DataclassesHook(Hook):

    @staticmethod
    def is_object(obj: object) -> bool:
        return is_dataclass(obj)

    @staticmethod
    def load_value(ver: Version, obj: object, parent=PropertyPath()):
        def _setattr(name, value):
            super(type(obj), obj).__setattr__(name, value)
            ver.update_props(parent.attr(name))

        obj.__setattr__ = _setattr


@dataclass
class B:
    b: int


@dataclass
class A:
    a: int
    b: B
