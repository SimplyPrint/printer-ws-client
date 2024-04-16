import unittest
from dataclasses import dataclass, field
from typing import List

from state_effect.property_path import props, PropertyNode, PropertyPath, as_path, p


class TestPropertyPath(unittest.TestCase):
    def test_simple(self):
        d = {
            'a': 'a',
            'b': 'g',
            'c': {
                'q': [1, 2, 3]
            }
        }

        path_for_a = as_path(p["a"])
        path_for_g = as_path(p["b"])
        path_for_3 = as_path(p["c"]["q"][2])

        self.assertEqual(path_for_a.resolve(d), 'a')
        self.assertEqual(path_for_g.resolve(d), 'g')
        self.assertEqual(path_for_3.resolve(d), 3)

    def test_object_hash(self):
        class MyCustomClass:
            ...

        instance = MyCustomClass()

        d = {
            instance: 10
        }

        self.assertIsNone(d.get(MyCustomClass()))
        self.assertEqual(d.get(instance), 10)

        path = PropertyPath().idx(instance)

        self.assertEqual(path.resolve(d), 10)
        self.assertEqual(as_path(p[instance]).resolve(d), 10)
        self.assertRaises(KeyError, lambda: as_path(p[MyCustomClass()]).resolve(d))

    def test_path_hash(self):
        p1 = p.cool_path[1]
        p2 = p.cool_path[1]
        p3 = as_path(p).attr('cool_path').idx(1)
        p4 = p.cool_path

        self.assertEqual(hash(p1), hash(p2))
        self.assertEqual(hash(p1), hash(p3))
        self.assertNotEqual(hash(p1), hash(p4))

        d = {p1: 'value'}

        self.assertEqual(d[p1], d[p2])

    def test_recursive(self):
        @dataclass
        class A:
            a: "A"

        props(A, A)

        self.assertTrue(isinstance(A.a, PropertyNode))
        self.assertFalse(hasattr(A.a, "a"))

    def test_class(self):
        @dataclass
        class C:
            list: List['A']
            field: int = field(default=10)

        @dataclass
        class B:
            c: C
            list: List[int]

        @dataclass
        class A:
            b: B
            list: List[str]

        obj = A(list=['a', 'b', 'c'], b=B(list=[1, 2, 3], c=C(list=[])))
        obj.b.c.list.append(obj)

        path = PropertyPath().attr("b").attr("c").attr("list").idx(0)

        self.assertEqual(path.resolve(obj), obj)

    def test_props(self):
        @dataclass
        class Child:
            field: str

        @dataclass(slots=True)
        class State:
            i: int
            f: float
            s: str
            c: Child = field(default=None)

        s = State(i=1, f=1.0, s="a", c=Child(field="child"))

        StateProps = props(State)

        path = PropertyNode.as_path(StateProps.c.field)

        self.assertEqual(path.resolve(s), "child")

        s.c.field = "adult"

        self.assertEqual(path.resolve(s), "adult")
