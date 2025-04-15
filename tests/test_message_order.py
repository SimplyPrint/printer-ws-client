import unittest
import weakref

from simplyprint_ws_client import *
from simplyprint_ws_client.core._event_instrumentation import consume


class TestMessageOrder(unittest.TestCase):
    def setUp(self):
        self.client = Client(PrinterConfig.get_new())
        self.client.config.id = 1
        self.client.config.in_setup = False
        self.ctx = weakref.ref(self.client)

    def test_message_order_simple(self):
        msgs, _ = consume(self.client.printer)
        self.assertEqual(len(msgs), 0)

        self.client.printer.job_info.started = True
        self.client.printer.status = PrinterStatus.PRINTING

        # Assert the order of messages
        msgs, _ = consume(self.client.printer)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0].__class__, JobInfoMsg)
        self.assertEqual(msgs[1].__class__, StateChangeMsg)
