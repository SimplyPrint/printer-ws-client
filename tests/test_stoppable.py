import unittest
from typing import List

from simplyprint_ws_client.shared.utils.stoppable import StoppableThread


class StoppableTaskExample(StoppableThread):
    state: List[int]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = []

    def run(self):
        self.state.append(0)

        while not self.is_stopped():
            self.wait()
            self.state.append(1)

        self.state.append(2)


class TestStoppable(unittest.TestCase):
    def test_parent_stoppable_stop(self):
        parent = StoppableTaskExample()
        child = StoppableTaskExample(parent_stoppable=parent)

        self.assertFalse(parent.is_stopped())
        self.assertFalse(child.is_stopped())

        parent.start()
        child.start()

        self.assertEqual(parent.state, [0])
        self.assertEqual(child.state, [0])

        parent.stop()
        parent.join()
        child.join()

        self.assertEqual(parent.state, [0, 1, 2])
        self.assertEqual(child.state, [0, 1, 2])

    def test_child_stoppable_stop(self):
        parent = StoppableTaskExample()

        child = StoppableTaskExample(parent_stoppable=parent)

        self.assertFalse(parent.is_stopped())
        self.assertFalse(child.is_stopped())
        self.assertEqual(parent.state, [])
        self.assertEqual(child.state, [])

        parent.start()
        child.start()

        self.assertEqual(parent.state, [0])
        self.assertEqual(child.state, [0])

        child.stop()
        child.join()

        self.assertEqual(child.state, [0, 1, 2])

        parent.stop()
        parent.join()

        self.assertTrue(parent.state.count(0) == 1)
        # Not guaranteed to hit 1 twice, but at least once.
        self.assertTrue(1 <= parent.state.count(1) <= 2)
        self.assertTrue(parent.state.count(2) == 1)

    def test_nested_stoppable(self):
        task1 = StoppableTaskExample()
        task2 = StoppableTaskExample(nested_stoppable=task1)

        self.assertFalse(task1.is_stopped())
        self.assertFalse(task2.is_stopped())

        task1.start()
        task2.start()
        task2.stop()

        self.assertTrue(task2.is_stopped())
        self.assertTrue(task1.is_stopped())

        task1.join()
        task2.join()

        self.assertEqual(task1.state, [0, 1, 2])
        self.assertEqual(task2.state, [0, 1, 2])
