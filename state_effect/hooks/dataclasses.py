from dataclasses import dataclass, is_dataclass, Field, fields
from typing import Iterable

from state_effect.hooks.base import Hook, ObjectField


def _convert_field_to_object_field(field: Field) -> ObjectField:
    """Converts a dataclass field to a custom object field (generic type)"""
    return ObjectField(field.name, field.type)


class DataclassHook(Hook):

    def is_valid_object(self, obj: object) -> bool:
        return is_dataclass(obj)

    def get_object_fields(self, obj: object) -> Iterable[ObjectField]:
        return map(_convert_field_to_object_field, fields(obj))


@dataclass
class B:
    b: int


@dataclass
class A:
    a: int
    b: B
