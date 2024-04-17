from pydantic import BaseModel

from state_effect.hooks.hook import Hook


class PydanticHook(Hook):
    ...


class B(BaseModel):
    b: int


class A(BaseModel):
    a: int
    b: B
