from typing import Iterable

from state_effect.hooks.base import Hook, ObjectField
from state_effect.version import Version


class DefaultHook(Hook):
    def is_valid_object(self, obj: object) -> bool:
        return hasattr(obj, '__class__') and (hasattr(obj, '__dict__') or hasattr(obj, '__slots__'))

    def get_object_fields(self, obj: object) -> Iterable[ObjectField]:
        assert obj.__annotations__, "Needs to be an annotated class"

        for name, annotation_type in obj.__annotations__.items():
            yield ObjectField(name, annotation_type)


class B:
    b: int

    def __init__(self, b=10):
        self.b = b


class A:
    a: int
    b: B

    def __init__(self, a=10, b=None):
        self.a = a
        self.b = b


if __name__ == '__main__':
    o = A(a=10, b=B(b=10))

    v = Version()
    hook = DefaultHook()

    hook.hook_recursive(v, o)

    print(o.a, v.has_changes())
    o.a = 11
    print(o.a, v.has_changes())
