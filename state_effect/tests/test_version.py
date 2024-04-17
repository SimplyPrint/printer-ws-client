import unittest
from dataclasses import dataclass

from state_effect.property_path import props
from state_effect.version import Version


class TestVersion(unittest.TestCase):

    def test_simple(self):
        @dataclass
        class C:
            a: int
            b: int

        ClassProps = props(C)

        c = C(a=1, b=0)
        v = Version()

        self.assertFalse(v.has_changes())

        v.update_props(ClassProps.a, ClassProps.b)

        self.assertTrue(v.has_changes())

        self.assertEqual(list(v.get_changes()), [(ClassProps.a, v.current), (ClassProps.b, v.current)])

        v.update_props(ClassProps.b)

        self.assertEqual(list(v.get_changes()), [(ClassProps.a, v.current - 1), (ClassProps.b, v.current)])
        self.assertEqual(v.get_changes_by_version(), {v.current - 1: {ClassProps.a}, v.current: {ClassProps.b}})

        v.mark_read()

        self.assertEqual(v.current, v.read_at)
        self.assertEqual(list(v.get_changes()), [])
