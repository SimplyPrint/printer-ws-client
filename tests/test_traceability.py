import unittest

from simplyprint_ws_client.client import Client
from simplyprint_ws_client.client.config import Config, PrinterConfig
from simplyprint_ws_client.utils import traceability


class TestTraceability(unittest.IsolatedAsyncioTestCase):
    async def test_client_traceability(self):
        class TestClient(Client):
            async def init(self):
                pass

            async def tick(self):
                pass

            async def stop(self):
                pass

        with traceability.enable_traceable():
            client = TestClient(config=PrinterConfig.get_new())

            class_traces = traceability.from_class(client)

            self.assertTrue(len(class_traces) == 0)

            client.connected = True

            class_traces = traceability.from_class(client)
            self.assertTrue("connected" in class_traces)
            connected_traces = class_traces["connected"]

            self.assertEqual(len(connected_traces.get_call_record()), 1)

            connected_record = connected_traces.call_record.pop()

            self.assertEqual(connected_record.args, (True,))

    def test_record_class_isolation(self):
        class TestClass:
            @traceability.traceable(with_retval=True)
            def traceable_function(self, a: int, b: int) -> int:
                return a + b

        test_instance_1 = TestClass()
        test_instance_2 = TestClass()

        with traceability.enable_traceable():
            test_instance_1.traceable_function(1, 2)
            test_instance_1.traceable_function(2, 3)
            test_instance_2.traceable_function(3, 4)

        trace_1 = traceability.from_class(test_instance_1)['traceable_function']
        trace_2 = traceability.from_class(test_instance_2)['traceable_function']

        self.assertTrue(trace_1 == traceability.from_func(test_instance_1.traceable_function))
        self.assertFalse(trace_1 == traceability.from_func(TestClass.traceable_function))
        self.assertFalse(trace_1 == trace_2)

        self.assertEqual(len(trace_1.get_call_record()), 2)
        self.assertEqual(len(trace_2.get_call_record()), 1)

    def test_record_traceability_property_getter_and_setter(self):
        class TestClass:
            def __init__(self):
                self._value = 0

            @property
            @traceability.traceable(with_retval=True)
            def value(self):
                return self._value

            @value.setter
            @traceability.traceable(with_args=True)
            def value(self, value):
                self._value = value

        test_instance = TestClass()

        with traceability.enable_traceable():
            test_instance.value = 1
            self.assertEqual(test_instance.value, 1)

        trace = traceability.from_class(test_instance).get('value')

        self.assertEqual(len(trace.get_call_record()), 2)

        trace_set_record = trace.call_record.popleft()

        self.assertEqual(trace_set_record.args, (1,))

        trace_get_record = trace.call_record.popleft()

        self.assertEqual(trace_get_record.retval, 1)

    def test_record_traceability(self):
        @traceability.traceable(with_retval=True)
        def traceable_function_a(a: int, b: int) -> int:
            return a + b

        @traceability.traceable(with_args=True, with_stack=True)
        def traceable_function_b(a: int, b: int, **kwargs) -> int:
            return a * b

        with traceability.enable_traceable():
            traceable_function_a(1, 2)
            traceable_function_b(1, 2)

        trace_a = traceability.from_func(traceable_function_a)
        trace_b = traceability.from_func(traceable_function_b)

        self.assertEqual(len(trace_a.get_call_record()), 1)
        self.assertEqual(len(trace_b.get_call_record()), 1)

        trace_a_record = trace_a.call_record.pop()
        trace_b_record = trace_b.call_record.pop()

        self.assertEqual(trace_a_record.args, None)
        self.assertEqual(trace_a_record.retval, 3)

        self.assertEqual(trace_b_record.args, (1, 2))
        self.assertEqual(trace_b_record.retval, None)

        with traceability.enable_traceable():
            traceable_function_b(1, 2, extra_custom_arg="test")

        trace_b_record = trace_b.call_record.pop()
        self.assertEqual(trace_b_record.args, (1, 2))
        self.assertEqual(trace_b_record.retval, None)
        self.assertEqual(trace_b_record.kwargs, {"extra_custom_arg": "test"})
        self.assertEqual(any('traceable_function_b(1, 2, extra_custom_arg="test")' in frame.line in frame for frame in
                             trace_b_record.stack),
                         True)

    def test_basic_traceability(self):
        @traceability.traceable
        def traceable_function(a: int, b: int) -> int:
            return a + b

        trace = traceability.from_func(traceable_function)

        self.assertEqual(trace.get_call_record(), [])
        self.assertEqual(trace.last_called, None)

        traceable_function(1, 2)

        self.assertEqual(trace.get_call_record(), [])
        self.assertEqual(trace.last_called, None)

        with traceability.enable_traceable():
            traceable_function(1, 2)

        self.assertNotEqual(trace.last_called, None)
