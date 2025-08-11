import unittest

from simplyprint_ws_client.events import Event
from simplyprint_ws_client.shared.events.predicate import (
    Constant,
    Reduce,
    Eq,
    Extract,
    Sel,
    And,
    EmptyPipe,
)
from simplyprint_ws_client.shared.events.property_path import p


class TestPredicate(unittest.TestCase):
    def test_simple(self):
        predicate = Constant(True)

        self.assertTrue(predicate())

        predicate = Constant(False)

        self.assertFalse(predicate())

    def test_conditional(self):
        a = [1, 2, 3]
        b = [4, 5, 6]

        predicate = (
            Sel(1)
            | Reduce(lambda x: filter(lambda y: y > 4, x))
            | Reduce(list)
            | Reduce(len)
            | Eq(2)
        )

        self.assertTrue(predicate(a, b))
        self.assertFalse(predicate(b, a))

    def test_property(self):
        class CustomEvent(Event):
            id: int = 1337
            name: str

            def __init__(self, name: str):
                self.name = name

        event_a = CustomEvent("a")
        event_b = CustomEvent("b")

        event_is_a = Sel(0) | And.chain(
            Extract(p.name) | Eq("a"), Extract(p.id) | Eq(1337)
        )

        self.assertTrue(event_is_a(event_a))
        self.assertFalse(event_is_a(event_b))

    def test_function_chains(self):
        def square(x):
            return x * x

        def add(x, y):
            return x + y

        def is_even(x):
            return x % 2 == 0

        predicate = EmptyPipe() | square | Eq(4)

        self.assertTrue(predicate(2))

        predicate = EmptyPipe() | add | Eq(4)

        self.assertTrue(predicate(2, 2))

    def test_predicate_equality(self):
        predicate = Constant(True)

        self.assertEqual(predicate, Constant(True))
        self.assertNotEqual(predicate, Constant(False))

        predicate = Reduce(lambda x: x) | Reduce(lambda x: x)

        self.assertEqual(predicate, Reduce(lambda x: x) | Reduce(lambda x: x))
        self.assertNotEqual(
            predicate, Reduce(lambda x: x) | Reduce(lambda x: x) | Reduce(lambda x: x)
        )

        predicate = Sel(0) | Reduce(lambda x: x)

        self.assertEqual(predicate, Sel(0) | Reduce(lambda x: x))
        self.assertNotEqual(predicate, Sel(1) | Reduce(lambda x: x))

        predicate = Extract(p.name) | Eq("a")

        self.assertEqual(predicate, Extract(p.name) | Eq("a"))
        self.assertNotEqual(predicate, Extract(p.id) | Eq(1337))

        predicate = And(Constant(True), Constant(True))

        self.assertEqual(predicate, And(Constant(True), Constant(True)))
        self.assertNotEqual(predicate, And(Constant(True), Constant(False)))
