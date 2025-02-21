import unittest
import weakref

from simplyprint_ws_client import Client, PrinterConfig, JobInfoState, PrinterState, JobInfoMsg


def job_state_consistent(state: JobInfoState):
    return sum(1 for key in JobInfoState.MUTUALLY_EXCLUSIVE_FIELDS if getattr(state, key)) <= 1


def build_job_state_msg(state: PrinterState) -> JobInfoMsg:
    return JobInfoMsg(data=dict(JobInfoMsg.build(state)))


class TestJobInfo(unittest.TestCase):
    def setUp(self):
        self.client = Client(PrinterConfig.get_new())
        self.ctx = weakref.ref(self.client)

    def test_exclusivity(self):
        state = JobInfoState()
        state.provide_context(self.ctx)

        self.assertEqual(state.model_changed_fields, set())
        self.assertTrue(job_state_consistent(state))

        state.started = True
        self.assertTrue(state.model_changed_fields & {"started"})
        self.assertTrue(job_state_consistent(state))

        state.model_reset_changed()
        state.started = True

        self.assertTrue(state.model_changed_fields & {"started"})
        self.assertTrue(job_state_consistent(state))

        state.failed = True

        self.assertTrue(state.failed)
        self.assertTrue(job_state_consistent(state))

        state.model_reset_changed()
        self.assertEqual(state.model_changed_fields, set())

    def test_generated_message(self):
        printer = PrinterState(config=self.client.config)
        printer.provide_context(self.ctx)
        state = printer.job_info

        self.assertEqual(state.model_changed_fields, set())
        self.assertTrue(job_state_consistent(state))

        self.assertEqual(dict(JobInfoMsg.build(printer)), {})

        state.started = True

        self.assertTrue(state.model_changed_fields & {"started"})
        self.assertTrue(job_state_consistent(state))

        msg = build_job_state_msg(printer)
        self.assertDictEqual(msg.model_dump(mode="json"), {"type": "job_info", "data": {"started": True}})
        msg.reset_changes(printer)
        self.assertEqual(state.model_changed_fields, set())

        state.started = False

        msg = build_job_state_msg(printer)
        self.assertDictEqual(msg.model_dump(mode="json"), {"type": "job_info"})
        msg.reset_changes(printer)
        self.assertEqual(state.model_changed_fields, set())

        state.cancelled = True
        state.progress = 10
        state.reprint = True

        msg = build_job_state_msg(printer)

        self.assertDictEqual(
            msg.model_dump(mode="json"),
            {"type": "job_info", "data": {"cancelled": True, "progress": 10, "reprint": 1}},
        )

        msg.reset_changes(printer)

        self.assertEqual(state.model_changed_fields, set())
        self.assertTrue(job_state_consistent(state))

        state.reprint = True

        msg = build_job_state_msg(printer)
        self.assertDictEqual(
            msg.model_dump(mode="json"),
            {"type": "job_info", "data": {"reprint": 1}},
        )

        msg.reset_changes(printer)
        self.assertEqual(state.model_changed_fields, set())
