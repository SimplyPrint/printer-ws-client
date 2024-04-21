"""Hook into any state objects given by the user."""

from abc import ABC, abstractmethod
from typing import NamedTuple, Iterable

from state_effect.property_path import PropertyPath


class ObjectField(NamedTuple):
    """Generic object field for all hook implementations"""
    name: str
    type: type


def default_hook(hook: 'Hook', klass: type, parent=PropertyPath()):
    """Directly override setattr"""
    _original__setattr__ = klass.__setattr__

    def __setattr__(self, name, value):
        _original__setattr__(self, name, value)

        ver.update_props(parent.attr(name))

        if hook.is_valid_object(value):
            hook.hook_recursive(ver, value)

    klass.__setattr__ = __setattr__


class Hook(ABC):
    @abstractmethod
    def is_valid_object(self, obj: object) -> bool:
        ...

    @abstractmethod
    def get_object_fields(self, obj: object) -> Iterable[ObjectField]:
        ...

    def hook_class(self, obj: type, parent=PropertyPath()):
        assert self.is_valid_object(obj), "Needs to be a valid object to hook."

        return default_hook(self, obj, parent)

    def hook_class_recursive(self, obj: type, parent=PropertyPath()):
        assert self.is_valid_object(obj)

        self.hook_class(obj, parent)

        for field in self.get_object_fields(obj):

            try:
                next_obj = getattr(obj, field.name)

            except AttributeError:
                continue

            if not self.is_valid_object(next_obj):
                continue

            self.hook_recursive(ver, next_obj, parent.attr(field.name))
