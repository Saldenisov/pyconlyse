"""Additional countdown belongs to actual HT exposure, never cold startup."""
import copy
import tempfile
import time
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.cooling_safety import AlarmJournal, CoolingSafety, utc
from tests.unit.test_acq_fault_diagnostic import Backend, sample
from tests.unit.test_acq_circulation_confirmation import Clock


class HTCoolingScopeTests(unittest.TestCase):
    def make(self):
        clock, backend = Clock(), Backend()
        backend.ht_feedback_verified, backend.ht_zero_tolerance_kv = True, .05
        runtime = AcquisitionControlRuntime(lambda: backend, clock=clock, remote_enabled=True)
        runtime._backend = _ObservedBackend(backend, runtime)
        runtime._state = "RUNNING"
        runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
        return runtime, backend, clock

    def read(self, runtime, clock, voltage=0., supply_on=False, red=False):
        value = sample(0.)
        value["banks"]["C2_NI6071E_AI"]["legacy_scaled_values"][7] = voltage
        value["banks"]["C4_DIO96_DI"]["values"][48] = not supply_on
        if red:
            value["banks"]["C3_DIO96_DI"]["values"][0] = True
        runtime._latest, runtime._received_at = value, clock.now
        runtime._sequence += 1
        runtime._run_cooling_guard(value)
        return value

    def test_cold_and_general_water_only_never_arm_or_count_down(self):
        runtime, backend, clock = self.make()
        for general in (False, True):
            runtime._general_stop_required = general
            for at, red in ((0., True), (1., False), (4., False), (5., True), (200., True)):
                clock.now = at
                self.read(runtime, clock, red=red)
                runtime._tick_cooling()
                alarm = runtime.snapshot()["cooling_safety"]
                self.assertFalse(alarm["experiment_scope"]["active"])
                self.assertFalse(alarm["active"])
                self.assertFalse(alarm["confirmation_required"])
                self.assertEqual(alarm["stop_state"], "NONE")
                self.assertIsNone(runtime._pending)
        self.assertEqual(backend.calls, [])

    def test_actual_ht_with_existing_red_asks_then_requests_stop_once_at_120_seconds(self):
        runtime, backend, clock = self.make()
        runtime._general_stop_required = True
        backend.operator_supervised_test = backend.operator_test_cold_attested = True
        self.read(runtime, clock, voltage=12., supply_on=True, red=True)
        alarm = runtime.snapshot()["cooling_safety"]
        self.assertTrue(alarm["experiment_scope"]["active"])
        self.assertTrue(alarm["confirmation_required"])
        self.assertEqual(alarm["remaining_seconds"], 120.)
        clock.now = 119.9
        runtime._tick_cooling()
        self.assertIsNone(runtime._pending)
        clock.now = 120.
        runtime._tick_cooling()
        self.assertEqual(runtime._pending, "general_stop")
        self.assertEqual(runtime.cooling.snapshot()["stop_state"], "REQUESTED")
        self.assertEqual(backend.calls, [])  # Enqueued only; no native call in watchdog.

    def test_actual_ht_green_then_red_uses_per_episode_confirmation(self):
        runtime, backend, clock = self.make()
        runtime._general_stop_required = True
        self.read(runtime, clock, voltage=10., supply_on=True)
        clock.now = 1.
        self.read(runtime, clock, voltage=10., supply_on=True, red=True)
        ids = [row["incident_id"] for row in runtime.cooling.snapshot()["confirmation_candidates"]]
        runtime.dispatch_remote("cooling.confirm_circulation", dict(incident_ids=ids))
        clock.now = 200.
        runtime._tick_cooling()
        self.assertIsNone(runtime._pending)
        self.assertFalse(runtime.cooling.snapshot()["countdown_required"])
        self.assertEqual(backend.calls, [])

    def test_ht_setpoint_or_software_ok_without_fresh_measured_ht_cannot_arm(self):
        for failure in ("zero", "supply_off", "unqualified", "missing_calibration", "nonfinite", "incomplete"):
            runtime, backend, clock = self.make()
            runtime._general_stop_required = True
            backend.ht_sequence_state = dict(command_known=True, current_command_kv=12.,
                supply_sequence_completed=True, pulses_sequence_completed=True)
            if failure == "unqualified": backend.ht_feedback_verified = False
            value = sample(12.)
            if failure == "zero": value["banks"]["C2_NI6071E_AI"]["legacy_scaled_values"][7] = 0.
            elif failure == "supply_off": value["banks"]["C4_DIO96_DI"]["values"][48] = True
            elif failure == "missing_calibration": value["banks"]["C2_NI6071E_AI"].pop("legacy_scaled_values")
            elif failure == "nonfinite": value["banks"]["C2_NI6071E_AI"]["legacy_scaled_values"][7] = float("nan")
            elif failure == "incomplete": value["banks"]["C4_DIO96_DI"]["values"] = []
            self.assertFalse(runtime._cooling_experiment_active(value, clock.now), failure)

    def test_stale_zero_or_owner_uncertainty_cannot_disarm_existing_exposure(self):
        runtime, backend, clock = self.make()
        runtime._general_stop_required = True
        self.read(runtime, clock, voltage=10., supply_on=True, red=True)
        zero = sample(0.)
        zero["banks"]["C4_DIO96_DI"]["values"][48] = True
        clock.now = 3.
        self.assertTrue(runtime._cooling_experiment_active(zero, 0.))
        backend.uncertain = True
        self.assertTrue(runtime._cooling_experiment_active(zero, clock.now))
        backend.uncertain = False
        backend.generation = "other-owner"
        self.assertTrue(runtime._cooling_experiment_active(zero, clock.now))

    def test_fresh_zero_supply_off_and_stopped_pulses_end_scope_without_clearing_native_fault(self):
        runtime, backend, clock = self.make()
        runtime._general_stop_required = True
        self.read(runtime, clock, voltage=10., supply_on=True, red=True)
        runtime._pulse_stop_required = True
        self.read(runtime, clock, red=True)
        self.assertTrue(runtime._cooling_ht_active)
        runtime._pulse_stop_required = False
        runtime._error, runtime._state = "real source stop fault", "FAULT"
        value = sample(0.)
        value["banks"]["C4_DIO96_DI"]["values"][48] = True
        runtime._observe_cooling_inputs(runtime._circuits, value, clock.now)
        alarm = runtime.cooling.snapshot()
        self.assertFalse(runtime._cooling_ht_active)
        self.assertFalse(alarm["active"])
        self.assertEqual(alarm["historical_incidents"][0]["historical_reason"], "HT_EXPERIMENT_INACTIVE")
        self.assertEqual((runtime._state, runtime._error), ("FAULT", "real source stop fault"))
        self.assertEqual(backend.calls, [])

    def test_previous_failed_cooling_countdown_is_history_before_initialize(self):
        with tempfile.TemporaryDirectory() as folder:
            path = folder + "/alarm.sqlite"
            old = AlarmJournal(path, "test")
            old.begin_session()
            previous = dict(incidents=dict(CANON=dict(circuit="CANON", incident_id="a" * 32,
                started_utc=utc(1000.), deadline_utc=utc(1120.), deadline_epoch=1120.,
                causes=[dict(signal="flow", bank="C4_IN_DIO96", index=19, raw=True)])),
                policy_version=2, stop_state="FAILED", stop_error="old Chroma stop failure")
            old.append(previous, dict(kind="SHUTDOWN_FAILED", error=previous["stop_error"]))
            old.end_session(True)
            old.close()
            alarm = CoolingSafety.with_journal(path, "test")
            runtime = AcquisitionControlRuntime(lambda: None, cooling=alarm)
            try:
                deadline = time.monotonic() + 3
                while not alarm.snapshot()["journal_ready"] and time.monotonic() < deadline:
                    time.sleep(.005)
                value = runtime.snapshot()
                current = value["cooling_safety"]
                self.assertEqual(value["state"], "IDLE")
                self.assertFalse(current["active"])
                self.assertEqual(current["stop_state"], "NONE")
                self.assertEqual(current["historical_incidents"][0]["prior_stop_error"], "old Chroma stop failure")
                self.assertFalse(alarm.tick(True))
                self.assertIsNone(runtime._backend)
            finally:
                alarm.close(3)


if __name__ == "__main__":
    unittest.main()
