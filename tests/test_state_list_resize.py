import functools
import random
import unittest
from concurrent.futures.thread import ThreadPoolExecutor

from simplyprint_ws_client import PrinterState, PrinterConfig


def _assert_printer_state_consistent(printer: PrinterState):
    # Ensure that the internal state of the printer is consistent
    assert printer.tool_count >= 1
    assert printer.tool_count <= 255

    for tool in printer.tools:
        assert tool.material_count >= 1
        assert tool.material_count <= 255

    for i, tool in enumerate(printer.tools):
        assert tool.nozzle == i, f"Tool index mismatch: expected {i}, got {tool.nozzle} {printer.tools=}"
        for j, material in enumerate(tool.materials):
            assert material.ext == j, (
                f"Material index mismatch for tool {i}, material {j}: "
                f"expected {j}, got {material.ext}"
            )
            assert material.nozzle == i, (
                f"Material tool index mismatch for tool {i}, material {j}: "
                f"expected {i}, got {material.nozzle}"
                f" {printer.tools=}"
            )


class TestStateListResize(unittest.TestCase):
    def setUp(self):
        self.printer = PrinterState(config=PrinterConfig.get_new())

    def _test_state_list_resize_by_property(
            self, obj: object, property_name: str, n=1024, m=16
    ):
        # Fuzz material_count and nozzle_count properties
        # with random numbers between 1 and 255 and make sure
        # no assertions fail. Size up and down.

        def safe_rand(min_value, max_value):
            return (
                random.randint(min_value, max_value)
                if min_value < max_value
                else min_value
            )

        for i in range(n):
            s = getattr(obj, property_name)

            if i % 2 == 0:
                # Size up
                s = safe_rand(s or 1, m)
            else:
                # Size down
                s = safe_rand(1, s)

            setattr(obj, property_name, s)

            _assert_printer_state_consistent(self.printer)

    def _test_state_list_resize_by_property_multithreaded(
            self, obj: object, property_name: str, n=1024, tc=10
    ):
        with ThreadPoolExecutor(max_workers=tc) as executor:
            futures = []

            for i in range(tc):
                future = executor.submit(
                    functools.partial(
                        self._test_state_list_resize_by_property, obj, property_name, n
                    )
                )

                futures.append(future)

            for future in futures:
                future.result()

    def test_state_list_resize(self):
        self._test_state_list_resize_by_property(self.printer, "tool_count")
        self._test_state_list_resize_by_property(self.printer.tool(), "material_count")

    def test_state_list_resize_multithreaded(self):
        with ThreadPoolExecutor(2) as executor:
            f1 = executor.submit(
                self._test_state_list_resize_by_property_multithreaded,
                self.printer,
                "tool_count",
            )
            f2 = executor.submit(
                self._test_state_list_resize_by_property_multithreaded,
                self.printer.tool(),
                "material_count",
            )
            f1.result()
            f2.result()
