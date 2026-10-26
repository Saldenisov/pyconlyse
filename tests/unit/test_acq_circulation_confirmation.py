"""Authenticated incident confirmation is software-only; actual Python 3.4."""
import copy
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities, require_command
from tests.unit.test_acq_fault_diagnostic import Backend, Wake, sample


OPERATION = "cooling.confirm_circulation"


class Clock(object):
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now


class CirculationConfirmationTests(unittest.TestCase):
    def make_runtime(self):
        clock, backend = Clock(), Backend()
        backend.ht_feedback_verified, backend.ht_zero_tolerance_kv = True, .05
        backend.stage_controls_verified = False
        runtime = AcquisitionControlRuntime(lambda: backend, clock=clock, remote_enabled=True)
        runtime._backend = _ObservedBackend(backend, runtime)
        runtime._state, runtime._general_stop_required = "RUNNING", True
        runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
        for at in (0., 1., 2., 3.):
            clock.now = at
            value = sample(1.)
            value["banks"]["C3_DIO96_DI"]["values"][0] = at == 3.
            runtime._latest, runtime._received_at = value, at
            runtime._sequence += 1
            runtime._run_cooling_guard(value)
        ids = [item["incident_id"] for item in runtime.cooling.snapshot()["confirmation_candidates"]]
        self.assertEqual(len(ids), 1)
        return runtime, clock, backend, dict(incident_ids=ids)

    def request(self, runtime, value, identifier="a"):
        return dict(command_id=identifier * 32, session_id=runtime._identity["session_id"],
            expected_revision=runtime._state_revision, operation=OPERATION,
            operator_confirmed=True, value=copy.deepcopy(value))

    def test_capability_and_dispatch_are_independent_of_energy_start_permits(self):
        runtime, clock, backend, value = self.make_runtime()
        before = runtime.snapshot()
        self.assertTrue(before["control"]["capabilities"][OPERATION]["enabled"])
        self.assertFalse(before["control"]["capabilities"]["chauffage.start"]["enabled"])
        received, sequence, revision = runtime._received_at, runtime._sequence, runtime._state_revision
        result = runtime.dispatch_remote(OPERATION, value)
        self.assertEqual(result, dict(completed_without_hardware=True,
            confirmed_incident_ids=value["incident_ids"]))
        self.assertEqual(runtime._state_revision, revision)
        self.assertEqual((runtime._received_at, runtime._sequence), (received, sequence))
        self.assertIsNone(runtime._pending)
        self.assertIsNone(runtime._operation)
        self.assertEqual(backend.calls, [])
        after = runtime.snapshot()
        self.assertTrue(after["cooling_safety"]["active"])
        self.assertFalse(after["cooling_safety"]["confirmation_required"])
        self.assertFalse(after["cooling_safety"]["countdown_required"])
        self.assertEqual(after["cooling_safety"]["circuits"][0]["confirmed_by"], "authenticated_remote_operator")
        self.assertFalse(after["control"]["capabilities"]["chauffage.start"]["enabled"])
        clock.now = 200.
        runtime._tick_cooling()
        self.assertIsNone(runtime._pending)
        self.assertEqual(backend.calls, [])

    def test_confirmation_may_run_during_known_nonstopping_owner_execution(self):
        runtime, clock, backend, value = self.make_runtime()
        runtime._state, runtime._operation = "EXECUTING", "acq.stage.chauffage.start"
        runtime._received_at = -100.  # No fresh measurement is invented by manual confirmation.
        backend.worker_state, backend.request_id = "EXECUTING_EXECUTE_STAGE", 7
        self.assertTrue(runtime.snapshot()["control"]["capabilities"][OPERATION]["enabled"])
        revision, pending = runtime._state_revision, runtime._pending
        runtime.dispatch_remote(OPERATION, value)
        self.assertEqual((runtime._state_revision, runtime._pending), (revision, pending))
        self.assertFalse(runtime._cancel.is_set())
        self.assertEqual(runtime._operation, "acq.stage.chauffage.start")
        self.assertEqual(runtime._received_at, -100.)
        self.assertEqual(backend.calls, [])

    def test_confirmation_preserves_entered_procedure_context_and_later_measurement(self):
        runtime, clock, backend, value = self.make_runtime()
        operation = "chauffage.start"
        runtime._state, runtime._operation = "EXECUTING", "acq.stage." + operation
        runtime._received_at = None
        backend.worker_state, backend.request_id = "EXECUTING_EXECUTE_STAGE", 7
        initial_revision, initial_sequence = runtime._state_revision, runtime._sequence
        def executing_stage(name, cancel, operator_confirmed=False):
            backend.calls.append("already_running_stage")
            context = copy.deepcopy(runtime._backend._context)
            runtime.dispatch_remote(OPERATION, value)
            self.assertEqual(backend.calls, ["already_running_stage"])
            self.assertEqual(runtime._state_revision, initial_revision)
            self.assertIsNone(runtime._received_at)
            self.assertIsNone(runtime._pending)
            self.assertFalse(cancel.is_set())
            self.assertTrue(runtime._observation_context_current(dict(
                runtime_operation_context=context, worker_generation=backend.generation)))
            backend.observer(dict(sample=sample(2.), sample_age_seconds=0., safe_to_sample=True,
                                  worker_generation=backend.generation))
        backend.execute_stage = executing_stage
        runtime._backend.execute_stage(operation, runtime._cancel, operator_confirmed=True)
        self.assertEqual(runtime._state, "EXECUTING")
        self.assertEqual(runtime._operation, "acq.stage." + operation)
        self.assertEqual(runtime._sequence, initial_sequence + 1)
        self.assertTrue(runtime.try_telemetry_snapshot()["measurement_current"])

    def test_fault_requires_diagnostic_proof_and_confirmation_keeps_original_fault(self):
        runtime, clock, backend, value = self.make_runtime()
        runtime._procedure_fault(RuntimeError("cooling timeout"))
        self.assertFalse(runtime.snapshot()["control"]["capabilities"][OPERATION]["enabled"])
        runtime._wake = Wake(runtime, 1)
        runtime._run()
        runtime._state = "FAULT"
        self.assertTrue(runtime.snapshot()["control"]["capabilities"][OPERATION]["enabled"])
        before = runtime._error, runtime._received_at, runtime._sequence
        runtime.dispatch_remote(OPERATION, value)
        self.assertEqual(runtime._state, "FAULT")
        self.assertEqual((runtime._error, runtime._received_at, runtime._sequence), before)
        self.assertEqual(backend.calls, ["read"])

    def test_metadata_stop_recovery_expiry_and_ownership_barriers_remain(self):
        for failure in ("cached", "local", "stop", "close", "cancel", "uncertain", "recovery", "expiry", "requested"):
            runtime, clock, backend, command = self.make_runtime()
            value = runtime.snapshot()
            if failure == "cached": value.update(application_view_current=False, application_view_age_seconds=2.)
            elif failure == "local": value["local_request_pending"] = "deinitialize"
            elif failure == "stop": value["current_operation"] = "acq.stage.chauffage.stop"
            elif failure == "close": value["pending_operation"] = "close"
            elif failure == "cancel": value["cancellation_requested"] = True
            elif failure == "uncertain": value["native_isolation"]["ownership_uncertain"] = True
            elif failure == "recovery": value["recovery"]["required"] = True
            elif failure == "expiry": value["cooling_safety"]["confirmation_candidates"][0]["remaining_seconds"] = 0.
            else: value["cooling_safety"]["stop_state"] = "REQUESTED"
            self.assertFalse(command_capabilities(value)[OPERATION]["enabled"], failure)
            self.assertRaises(RuntimeError, require_command, value, OPERATION, command)
            self.assertEqual(backend.calls, [])

    def test_exact_current_incident_ids_and_deadline_are_rechecked_at_dispatch(self):
        runtime, clock, backend, value = self.make_runtime()
        stale = dict(incident_ids=["f" * 32])
        self.assertRaises(RuntimeError, runtime.dispatch_remote, OPERATION, stale)
        clock.now = 123.
        self.assertRaises(RuntimeError, runtime.dispatch_remote, OPERATION, value)
        self.assertFalse(runtime.cooling.snapshot()["circuits"][0]["confirmed"])
        self.assertEqual(backend.calls, [])

    def test_broker_completes_once_without_queue_and_rejects_old_incident(self):
        runtime, clock, backend, value = self.make_runtime()
        request = self.request(runtime, value)
        lease = runtime.broker.snapshot(issue_lease=True)["lease"]
        old_lease = runtime.broker.snapshot(issue_lease=True)["lease"]
        result = runtime.broker.submit(request, lease)
        self.assertEqual(result["outcome"], "COMPLETED")
        self.assertTrue(result["operator_confirmation_only"])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertFalse(result["hardware_writes"])
        duplicate = runtime.broker.submit(request, None)
        self.assertTrue(duplicate["duplicate"])
        old_request = copy.deepcopy(request)
        old_request["command_id"] = "b" * 32
        rejected = runtime.broker.submit(old_request, old_lease)
        self.assertEqual(rejected["outcome"], "REJECTED")
        self.assertIsNone(runtime._pending)
        self.assertEqual(backend.calls, [])


if __name__ == "__main__":
    unittest.main()
