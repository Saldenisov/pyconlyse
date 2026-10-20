"""Named command protocol against fake local callbacks only; no NI or sockets."""
import copy
import threading
import unittest

from legacy.xp_acq_agent.elyse_agent.acquisition_command_admission import (
    CommandAdmission, CommandRejected, NAMED_OPERATIONS, validate_envelope,
)


class FakeRuntime(object):
    def __init__(self):
        self.session = "a" * 32
        self.revision = 4
        self.recovery_required = False
        self.lock = threading.RLock()

    def snapshot(self):
        return dict(session_id=self.session, state_revision=self.revision)

    def fenced_local_request(self, session, revision, callback):
        with self.lock:
            if session != self.session or revision != self.revision or self.recovery_required:
                raise RuntimeError("synthetic fence rejected")
            callback()
            self.revision += 1


def envelope(**changes):
    value = dict(schema_version=1, command_id="b" * 32, session_id="a" * 32,
                 expected_revision=4, operation="modulator.general.stop", operator_confirmed=True)
    value.update(changes)
    return value


class CommandAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.calls = []
        self.callbacks = {"modulator.general.stop": lambda: self.calls.append("stop")}

    def test_default_is_disabled_even_with_valid_callback(self):
        admission = CommandAdmission(self.runtime, self.callbacks)
        with self.assertRaisesRegex(CommandRejected, "DISABLED"):
            admission.submit(envelope())
        self.assertEqual(self.calls, [])

    def test_exact_named_shape_no_raw_writes_or_release_override(self):
        invalid = [envelope(operation="write_bank"), envelope(operator_confirmed=1),
                   envelope(operator_confirmed=False), envelope(schema_version=True),
                   envelope(expected_revision=True), envelope(expected_revision=-1),
                   envelope(command_id="B" * 32), envelope(session_id=""),
                   envelope(args={"C4": [True]}), envelope(electrical_off_confirmed=True)]
        for request in invalid:
            with self.assertRaises(CommandRejected):
                validate_envelope(request)
        self.assertEqual(len(NAMED_OPERATIONS), 5)

    def test_duplicate_replies_do_not_execute_again_after_revision_changed(self):
        admission = CommandAdmission(self.runtime, self.callbacks, enabled=True)
        first = admission.submit(envelope())
        self.assertEqual(first["outcome"], "DISPATCHED")
        self.assertFalse(first["hardware_acknowledged"])
        first["outcome"] = "corrupted externally"
        repeated = admission.submit(envelope())
        self.assertTrue(repeated["duplicate"])
        self.assertEqual(repeated["outcome"], "DISPATCHED")
        self.assertEqual(self.calls, ["stop"])
        with self.assertRaisesRegex(CommandRejected, "REUSED"):
            admission.submit(envelope(expected_revision=5))

    def test_stale_revision_and_recovery_never_call_callback_or_auto_retry(self):
        for recovery, revision in ((False, 3), (True, 4)):
            self.runtime.recovery_required = recovery
            admission = CommandAdmission(self.runtime, self.callbacks, enabled=True)
            request = envelope(expected_revision=revision)
            result = admission.submit(request)
            self.assertEqual(result["outcome"], "INDETERMINATE")
            self.runtime.recovery_required = False
            self.runtime.revision = revision
            self.assertTrue(admission.submit(request)["duplicate"])
        self.assertEqual(self.calls, [])

    def test_partial_callback_failure_is_consumed_and_details_are_not_leaked(self):
        def failing():
            self.calls.append("partial")
            raise RuntimeError("private key or callback-specific text")
        admission = CommandAdmission(self.runtime, {"modulator.general.stop": failing}, enabled=True)
        reply = admission.submit(envelope())
        self.assertEqual(reply["outcome"], "INDETERMINATE")
        self.assertEqual(reply["error_type"], "RuntimeError")
        self.assertNotIn("private", str(reply))
        self.assertTrue(admission.submit(envelope())["duplicate"])
        self.assertEqual(self.calls, ["partial"])

    def test_old_session_cannot_replay_even_known_command(self):
        admission = CommandAdmission(self.runtime, self.callbacks, enabled=True)
        admission.submit(envelope())
        self.runtime.session = "c" * 32
        for request in (envelope(), envelope(session_id="c" * 32)):
            with self.assertRaisesRegex(CommandRejected, "SESSION_CHANGED"):
                admission.submit(request)
        self.assertEqual(self.calls, ["stop"])

    def test_full_ledger_never_evicts_old_commands(self):
        admission = CommandAdmission(self.runtime, self.callbacks, enabled=True, capacity=1)
        admission.submit(envelope())
        with self.assertRaisesRegex(CommandRejected, "LEDGER_FULL"):
            admission.submit(envelope(command_id="c" * 32, expected_revision=5))
        self.assertTrue(admission.submit(envelope())["duplicate"])
        self.assertEqual(self.calls, ["stop"])

    def test_concurrent_duplicate_attempts_are_serialized(self):
        admission = CommandAdmission(self.runtime, self.callbacks, enabled=True)
        replies = []
        workers = [threading.Thread(target=lambda: replies.append(admission.submit(envelope())))
                   for _ in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(1)
            self.assertFalse(worker.is_alive())
        self.assertEqual(len(replies), 8)
        self.assertEqual(sum(not row["duplicate"] for row in replies), 1)
        self.assertEqual(self.calls, ["stop"])

    def test_no_callback_is_inferred_and_input_not_mutated(self):
        request = envelope(operation="acquisition.initialize")
        before = copy.deepcopy(request)
        with self.assertRaisesRegex(CommandRejected, "NOT_INSTALLED"):
            CommandAdmission(self.runtime, enabled=True).submit(request)
        self.assertEqual(request, before)


if __name__ == "__main__":
    unittest.main()
