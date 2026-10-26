"""Accepted execution measurements feed cooling policy without NI callbacks."""
import copy
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from tests.unit.test_acq_circulation_confirmation import Clock, OPERATION
from tests.unit.test_acq_fault_diagnostic import Backend, sample


class ExecutionCoolingTests(unittest.TestCase):
    def make_runtime(self, arm=True):
        clock, backend = Clock(), Backend()
        backend.ht_feedback_verified, backend.ht_zero_tolerance_kv = True, .05
        runtime = AcquisitionControlRuntime(lambda: backend, clock=clock, remote_enabled=True)
        runtime._backend = _ObservedBackend(backend, runtime)
        runtime._state, runtime._general_stop_required = "RUNNING", True
        runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
        if arm:
            for at in (0., 1., 2.):
                clock.now = at
                runtime._latest, runtime._received_at = sample(1.), at
                runtime._sequence += 1
                runtime._run_cooling_guard(runtime._latest)
            self.assertEqual(runtime.cooling.snapshot()["armed_circuits"], ["CANON", "SECTION"])
        runtime._state, runtime._operation = "EXECUTING", "acq.stage.chauffage.start"
        runtime._received_at = None
        backend.worker_state, backend.request_id = "EXECUTING_EXECUTE_STAGE", 7
        return runtime, clock, backend

    def event(self, runtime, backend, reading, age=.25):
        return dict(sample=reading, sample_age_seconds=age, safe_to_sample=True,
            worker_generation=backend.generation, runtime_operation_context=dict(
                session_id=runtime._identity["session_id"], state_revision=runtime._state_revision,
                operation=runtime._operation, backend_identity=id(backend)))

    def test_red_execution_sample_prompts_before_long_procedure_returns_without_writes(self):
        runtime, clock, backend = self.make_runtime()
        original_revision = runtime._state_revision
        def long_stage(operation, cancel, operator_confirmed=False):
            backend.calls.append("entered_chauffage")
            clock.now = 3.
            reading = sample(2.)
            reading["banks"]["C3_DIO96_DI"]["values"][0] = True
            backend.observer(dict(sample=reading, sample_age_seconds=.75, safe_to_sample=True,
                                  worker_generation=backend.generation))
            # The real source procedure has not returned at this point.
            value = runtime.snapshot()
            alarm = value["cooling_safety"]
            self.assertTrue(alarm["active"])
            self.assertTrue(alarm["confirmation_required"])
            self.assertEqual(alarm["confirmation_candidates"][0]["circuit"], "CANON")
            self.assertEqual(alarm["remaining_seconds"], 120.)
            self.assertTrue(value["control"]["capabilities"][OPERATION]["enabled"])
            self.assertEqual(runtime._cooling_read_at, 2.25)
            self.assertEqual(runtime._received_at, 2.25)
            self.assertAlmostEqual(value["age_seconds"], .75)
            self.assertTrue(runtime._circuits["CANON"]["fault"])
            self.assertEqual(backend.calls, ["entered_chauffage"])
            self.assertEqual(runtime._state_revision, original_revision)
            self.assertEqual(runtime._operation, "acq.stage.chauffage.start")
            self.assertIsNone(runtime._pending)
            self.assertFalse(cancel.is_set())
        backend.execute_stage = long_stage
        runtime._backend.execute_stage("chauffage.start", runtime._cancel, operator_confirmed=True)
        self.assertEqual(backend.calls, ["entered_chauffage"])

    def test_stale_wrong_owner_session_and_revision_samples_cannot_arm_cooling(self):
        for failure in ("age", "generation", "session", "revision", "unsafe", "incomplete"):
            runtime, clock, backend = self.make_runtime(arm=False)
            for at in (0., 3.):
                clock.now = at
                event = self.event(runtime, backend, sample(1.))
                if failure == "age": event["sample_age_seconds"] = 2.
                elif failure == "generation": event["worker_generation"] = "other-owner"
                elif failure == "session": event["runtime_operation_context"]["session_id"] = "f" * 32
                elif failure == "revision": event["runtime_operation_context"]["state_revision"] -= 1
                elif failure == "unsafe": event["safe_to_sample"] = False
                else: event["sample"]["banks"].pop("C3_DIO96_DI")
                runtime.observe_execution(event)
            self.assertEqual(runtime.cooling.snapshot()["armed_circuits"], [], failure)
            self.assertFalse(runtime.cooling.snapshot()["active"], failure)
            self.assertIsNone(runtime._cooling_read_at, failure)
            self.assertEqual(backend.calls, [], failure)

    def test_rejected_green_execution_samples_cannot_clear_active_incident(self):
        runtime, clock, backend = self.make_runtime()
        clock.now = 3.
        red = sample(1.)
        red["banks"]["C4_DIO96_DI"]["values"][19] = True
        runtime.observe_execution(self.event(runtime, backend, red))
        original = copy.deepcopy(runtime.cooling.snapshot()["circuits"])
        cooling_at, sequence = runtime._cooling_read_at, runtime._sequence
        for at in (4., 7.):
            clock.now = at
            stale = self.event(runtime, backend, sample(1.), age=2.)
            runtime.observe_execution(stale)
            wrong = self.event(runtime, backend, sample(1.))
            wrong["worker_generation"] = "other-owner"
            runtime.observe_execution(wrong)
        after = runtime.cooling.snapshot()
        self.assertTrue(after["active"])
        self.assertEqual(after["circuits"][0]["incident_id"], original[0]["incident_id"])
        self.assertEqual(runtime._cooling_read_at, cooling_at)
        self.assertEqual(runtime._sequence, sequence)
        self.assertTrue(runtime._circuits["CANON"]["fault"])
        self.assertEqual(backend.calls, [])


if __name__ == "__main__":
    unittest.main()
