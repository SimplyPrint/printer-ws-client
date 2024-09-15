import unittest

from simplyprint_ws_client.client.protocol.client_events import JobInfoEvent
from simplyprint_ws_client.client.state import PrinterState


class TestJobInfoEvent(unittest.TestCase):

    def test_simple(self):
        state = PrinterState()

        state.job_info.progress = 0.0
        state.job_info.time = 0
        state.job_info.initial_estimate = 0
        state.job_info.cancelled = False
        state.job_info.finished = False
        state.job_info.failed = False
        state.job_info.filename = "test.gcode"

        event = JobInfoEvent(JobInfoEvent.build(state))

        self.assertEqual(event.data, {"filename": "test.gcode"})

        # Increment version
        event.on_sent()

        state.job_info.finished = True

        self.assertEqual(state.job_info.has_changed("finished"), True)
        event = JobInfoEvent(JobInfoEvent.build(state))
        self.assertEqual(event.data, {"finished": True})

        event.on_sent()

        state.job_info.finished = True

        self.assertEqual(state.job_info.has_changed("finished"), True)
        event = JobInfoEvent(JobInfoEvent.build(state))
        self.assertEqual(event.data, {"finished": True})
