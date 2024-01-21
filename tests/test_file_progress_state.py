import unittest

from traitlets import Instance

from simplyprint_ws_client.events.client_events import FileProgressEvent
from simplyprint_ws_client.state.printer import FileProgressState, PrinterFileProgressState
from simplyprint_ws_client.state.root_state import RootState


class TestState(RootState):
    file_progress: PrinterFileProgressState = Instance(PrinterFileProgressState)

    def __init__(self, **kwargs):
        super().__init__(
            file_progress=PrinterFileProgressState(),
        )


class TestJobInfoState(unittest.TestCase):
    def test_basic_state(self):
        state = TestState()
        state.file_progress.state = FileProgressState.DOWNLOADING
        state.file_progress.percent = 50

        event = next(state._build_events())

        self.assertIsInstance(event, FileProgressEvent)

        self.assertDictEqual(dict(event.build()), {
            'state': 'downloading',
            'percent': 50.0,
        })

        state.file_progress.state = FileProgressState.READY
        state.file_progress.percent = 100

        event = next(state._build_events())

        self.assertIsInstance(event, FileProgressEvent)
        self.assertDictEqual(dict(event.build()), {
            'state': 'ready',
        })

        state.file_progress.state = FileProgressState.ERROR
        state.file_progress.message = "Something went wrong"

        event = next(state._build_events())

        self.assertIsInstance(event, FileProgressEvent)

        self.assertDictEqual(dict(event.build()), {
            'state': 'error',
            'message': "Something went wrong",
        })
