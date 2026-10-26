"""Authenticated per-incident operator acknowledgment; no NI or network."""
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.command_protocol import validate_request
from legacy.xp_acq_control.elyse_agent.command_broker import CommandBroker
from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView


def request():
    return dict(command_id="c" * 32, session_id="a" * 32, expected_revision=2,
        operation="cooling.confirm_circulation", operator_confirmed=True,
        value=dict(incident_ids=["e" * 32]))


class CirculationProtocolTests(unittest.TestCase):
    def test_application_cache_cannot_offer_expired_incident_with_current_metadata(self):
        from tests.unit.test_acq_circulation_confirmation import CirculationConfirmationTests
        runtime, clock, backend, confirmation = CirculationConfirmationTests().make_runtime()
        clock.now = 122.9
        cache = ApplicationView(runtime, clock=clock)
        cache.capture_once()
        self.assertTrue(cache.snapshot()["control"]["capabilities"]["cooling.confirm_circulation"]["enabled"])
        clock.now = 123.1
        value = cache.snapshot()
        self.assertTrue(value["application_view_current"])
        self.assertFalse(value["cooling_safety"]["confirmation_required"])
        self.assertFalse(value["control"]["capabilities"]["cooling.confirm_circulation"]["enabled"])
        self.assertEqual(backend.calls, [])

    def test_exact_per_incident_payload_detached_and_no_client_operator_identity(self):
        value = request()
        result = validate_request(value)
        self.assertEqual(result, value)
        result["value"]["incident_ids"].append("f" * 32)
        self.assertEqual(value["value"]["incident_ids"], ["e" * 32])
        value["value"]["operator"] = "untrusted-browser-user"
        self.assertRaises(ValueError, validate_request, value)

    def test_empty_duplicate_unknown_or_unbounded_scope_is_rejected(self):
        for ids in ([], ["e" * 32] * 2, ["e" * 32] * 3, ["all"], [True], "e" * 32):
            with self.subTest(ids=ids):
                value = request()
                value["value"]["incident_ids"] = ids
                self.assertRaises(ValueError, validate_request, value)

    def test_broker_records_immediate_software_completion_once_without_owner_queue(self):
        class Runtime(object):
            def __init__(self):
                self._lock = threading.RLock()
                self._identity = dict(session_id="a" * 32)
                self._state_revision = 2
                self._state, self._pending, self._operation = "RUNNING", None, None
                self.calls = []
            def fenced_local_request(self, session, revision, callback):
                if session != self._identity["session_id"] or revision != self._state_revision:
                    raise RuntimeError("RUNTIME_CONTEXT_CHANGED")
                return callback()
            def dispatch_remote(self, operation, value):
                self.calls.append((operation, value))
                self._state_revision += 1
                return dict(completed_without_hardware=True,
                            confirmed_incident_ids=value["incident_ids"])
        runtime = Runtime()
        broker = CommandBroker(runtime, enabled=True, clock=lambda: 10.)
        lease = broker.issue_lease_nonblocking()
        result = broker.submit(request(), lease)
        self.assertEqual(result["outcome"], "COMPLETED")
        self.assertTrue(result["operator_confirmation_only"])
        self.assertFalse(result["hardware_writes"])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertTrue(broker.submit(request(), lease)["duplicate"])
        self.assertEqual(len(runtime.calls), 1)
        self.assertIsNone(runtime._pending)
        self.assertIsNone(runtime._operation)


if __name__ == "__main__":
    unittest.main()
