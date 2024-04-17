from attrs import define

from state_effect.hooks.hook import Hook


class AttrsHook(Hook):
    ...


@define
class B:
    b: int


@define
class A:
    a: int
    b: B
