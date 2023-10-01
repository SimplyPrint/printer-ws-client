import unittest

from traitlets import Enum, Instance
from simplyprint_ws_client.events.client_events import JobInfoEvent, StateChangeEvent
from simplyprint_ws_client.printer import JobInfoState, PrinterStatus

from simplyprint_ws_client.state import RootState

class TestState(RootState):
    status: PrinterStatus = Enum(PrinterStatus)
    job_info: JobInfoState = Instance(JobInfoState)

    def __init__(self, **kwargs):
        super().__init__(
            status=PrinterStatus.OFFLINE,
            job_info=JobInfoState(),
        )

    event_map = {
        "status": StateChangeEvent,
    }

class TestJobInfoState(unittest.TestCase):
    def test_basic_state(self):
        state = TestState()
        
        self.assertEqual(list(map(lambda x: x.__class__, state._build_events())), [
            StateChangeEvent,
        ])

        self.assertEqual(state.status, PrinterStatus.OFFLINE)

    def test_status_change(self):
        state = TestState()
        state.status = PrinterStatus.PRINTING

        self.assertEqual(list(map(lambda x: x.__class__, state._build_events())), [
            StateChangeEvent,
        ])
        
        self.assertEqual(state.status, PrinterStatus.PRINTING)

    def test_combined_ordering(self):
        state = TestState()
        state.status = PrinterStatus.PRINTING
        state.job_info.started = True

        # Ensure the order of the events is correct
        self.assertEqual(list(map(lambda x: x.__class__, state._build_events())), [
            StateChangeEvent,
            JobInfoEvent,
        ])
        
        self.assertEqual(state.status, PrinterStatus.PRINTING)

    def test_single_bool_output(self):
        state = TestState()

        # Class identifier being tracked
        identifier = id(state.job_info)

        # Consume all initial events
        _ = list(state._build_events())

        state.job_info.started = True
        
        # Retrieve changeset
        self.assertEqual(state._changed_fields[identifier], set(["started"]))

        state.job_info.finished = True

        self.assertEqual(state._changed_fields[identifier], set(["started", "finished"]))

        # Consume event
        event = next(state._build_events())

        self.assertEqual(event.__class__, JobInfoEvent)

        event_data = dict(event.generate_data())

        self.assertEqual(event_data.keys(), set(["finished"]))