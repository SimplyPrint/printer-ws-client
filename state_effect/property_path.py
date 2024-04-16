"""A property path is a way to reference nested variables on an object.

It supports attributes and indices and every change is immutable.

"""

from dataclasses import is_dataclass, Field, fields
from typing import Optional, TypeVar, List, Hashable, get_origin, get_args, Dict, Set, Generic, Union, Self, cast, Any


class _Attribute(str):
    """A part of a path - field name"""
    ...


class AnyIdx:
    """Special index sentinel that is reserved for derive.

    When used with resolve it will throw an KeyError unless defined.
    """

    __slots__ = []


Indexable = Hashable | int | slice
Shard = _Attribute | Indexable


class PropertyPath(object):
    """Representation of a property path where parts are called "Shards"

    Can be used to query objects for values. Immutable builder functions.
    """

    __slots__ = ('__path', '__hash')

    __path: List[Shard]
    __hash: int

    def __init__(self, path=None):
        self.__path = path or []
        self.__hash = hash(str(self))

    def __str__(self) -> str:
        return ''.join([
            f".{shard}" if isinstance(shard, _Attribute) else f"[{repr(shard)}]"
            for shard in self.__path
        ])

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {str(self)}>"

    def __eq__(self, other) -> bool:
        if not isinstance(other, PropertyPath):
            return False

        return self.__hash == other.__hash

    def __hash__(self) -> int:
        return self.__hash

    def as_path(self):
        return PropertyPath(self.__path)

    def pop(self, *args, **kwargs) -> Self:
        items = self.__path.copy()
        items.pop(*args, **kwargs)
        return self.__class__(items)

    def push(self, item) -> Self:
        items = self.__path.copy()
        items.append(item)
        return self.__class__(items)

    def resolve(self, current: object) -> Any:
        for shard in self.__path:
            if isinstance(shard, _Attribute):
                current = getattr(current, shard)
            else:
                current = current[shard]

        return current

    def attr(self, item: str) -> Self:
        return self.push(_Attribute(item))

    def idx(self, item: Indexable) -> Self:
        return self.push(item)


class PropertyPathBuilder(PropertyPath):
    """A path to a property, with builder functions.

    Allows for this object to be given to a function to replicate
    all the property accesses it received.
    """

    def __getattr__(self, item: str) -> Self:
        return super().push(_Attribute(item))

    def __getitem__(self, item: Indexable) -> Self:
        return super().push(item)


def as_path(builder: PropertyPathBuilder) -> PropertyPath:
    return cast(PropertyPath, super(type(builder), builder)).as_path()


p = PropertyPathBuilder()


class PropertyNode:
    _field: Optional[Field]
    _path: PropertyPath
    _nested_node: Optional["PropertyNode"]

    def __new__(cls, *args, slots=None, **kwargs):
        if slots:
            cls.__slots__ = ('_field', '_path', '_nested_node') + tuple(slots)

        return super().__new__(cls)

    def __init__(self, f: Optional[Field], p: PropertyPath, slots=None):
        self._field = f
        self._path = p
        self._nested_node = None

    def __getitem__(self, item):
        if item != AnyIdx:
            raise IndexError()

        if not self._nested_node:
            raise ValueError()

        return self._nested_node

    def __setitem__(self, key, value):
        if key != AnyIdx:
            raise IndexError()

        if not isinstance(value, PropertyNode):
            raise ValueError()

        self._nested_node = value

    @staticmethod
    def as_path(node: "PropertyNode"):
        return node._path


_T = TypeVar('_T')


def props(src: _T, dst=None, path=None) -> _T:
    """Traverse a dataclass type and generate a tree of field paths based
    on its annotations.

    Used to reference a path to an object. This can be cached.

    @dataclass
    class MyClass:
        a: int
        b: str


    paths(MyClass).a (FieldNode with path 'a')

    It can also apply the shortcuts directly on the clas object

    paths(MyClass, MyClass)

    MyClass.a (FieldNode with path 'a')

    Most commonly

    MyClassProps = paths(MyClass)

    And use that variable instead for the most pythonic experience.

    TODO: Extend to support more data models (plain, Pydantic, attrs, etc)
    TODO: Type this function correctly -> mirror of T on new type.
    TODO: Support more annotation types (Move 100% to annotations?)
    """

    assert is_dataclass(src), "Only supports dataclasses for now."

    if path is None:
        path = PropertyPath()

    field_list = fields(src)
    slot_fields = list(map(lambda f: f.name, field_list))

    if dst is None:
        dst = PropertyNode(None, path, slots=slot_fields)

    for f in field_list:
        # Ignore default values.
        try:
            if isinstance(getattr(dst, f.name), PropertyNode):
                continue
        except AttributeError:
            pass

        new_path = path.attr(f.name)
        field_node = PropertyNode(f, new_path, slots=slot_fields)

        if is_dataclass(f.type):
            props(f.type, field_node, new_path)

        else:
            base_type = get_origin(f.type)
            base_type_args = get_args(f.type)

            if base_type in (Union, Generic):
                for t in base_type_args:
                    if not is_dataclass(t):
                        continue

                    props(t, field_node, new_path)

            elif base_type in (List, Dict, Set):
                new_path = new_path.idx(AnyIdx)
                nested_type = None

                for i, t in enumerate(base_type_args):
                    if base_type == Dict and i == 0:
                        continue

                    if not is_dataclass(t):
                        continue

                    nested_type = t

                if nested_type:
                    nested_field_list = fields(nested_type)
                    nested_field_slots = list(map(lambda f: f.name, nested_field_list))
                    nested_field_node = PropertyNode(f, new_path, slots=nested_field_slots)
                    field_node[AnyIdx] = nested_field_node
                    props(nested_field_node, f.name)

        setattr(dst, f.name, field_node)

    return dst
