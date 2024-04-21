from typing import Iterable

from pydantic import BaseModel

from state_effect.hooks.base import Hook, ObjectField


class PydanticHook(Hook):
    def is_valid_object(self, obj: object) -> bool:
        pass

    def get_object_fields(self, obj: object) -> Iterable[ObjectField]:
        pass


class B(BaseModel):
    b: int


class A(BaseModel):
    a: int
    b: B
