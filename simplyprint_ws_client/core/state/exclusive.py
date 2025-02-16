__all__ = ['Exclusive']

from typing import TypeVar, TYPE_CHECKING, TypeAlias

from pydantic import RootModel

T = TypeVar('T')

if TYPE_CHECKING:
    Exclusive: TypeAlias = T
else:
    class Exclusive(RootModel[T]):
        root: T

        def __hash__(self):
            return hash(self.root)

        def __eq__(self, other):
            """An exclusive object is only equal to itself."""
            if isinstance(other, Exclusive):
                return self is other

            return False

        def __bool__(self):
            return bool(self.root)

        def __repr__(self):
            return repr(self.root)