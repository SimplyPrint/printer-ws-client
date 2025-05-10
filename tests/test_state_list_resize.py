import functools
import random
import unittest
from concurrent.futures.thread import ThreadPoolExecutor

from simplyprint_ws_client import PrinterState, PrinterConfig


class TestStateListResize(unittest.TestCase):
    def setUp(self):
        self.printer = PrinterState(config=PrinterConfig.get_new())
        self.printer.nozzle_count = 1
        self.printer.material_count = 1

    def _test_state_list_resize_by_property(self, property_name: str, n=1024, m=16):
        # Fuzz material_count and nozzle_count properties
        # with random numbers between 1 and 255 and make sure
        # no assertions fail. Size up and down.

        def safe_rand(min_value, max_value):
            return random.randint(min_value, max_value) if min_value < max_value else min_value

        for i in range(n):
            s = getattr(self.printer, property_name)

            if i % 2 == 0:
                # Size up
                s = safe_rand(s or 1, m)
            else:
                # Size down
                s = safe_rand(1, s)

            setattr(self.printer, property_name, s)

    def _test_state_list_resize_by_property_multithreaded(self, property_name: str, n=1024, tc=10):
        with ThreadPoolExecutor(max_workers=tc) as executor:
            futures = []

            for i in range(tc):
                future = executor.submit(
                    functools.partial(self._test_state_list_resize_by_property, property_name, n)
                )

                futures.append(future)

            for future in futures:
                future.result()

    def test_state_list_resize(self):
        self._test_state_list_resize_by_property("material_count")
        self._test_state_list_resize_by_property("nozzle_count")

    def test_state_list_resize_multithreaded(self):
        with ThreadPoolExecutor(2) as executor:
            f1 = executor.submit(self._test_state_list_resize_by_property_multithreaded, "material_count")
            f2 = executor.submit(self._test_state_list_resize_by_property_multithreaded, "nozzle_count")
            f1.result()
            f2.result()
