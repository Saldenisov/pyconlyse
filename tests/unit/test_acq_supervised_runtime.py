"""Metadata-only operator test admission and owner-bound cooling; Python 3.4."""
import threading
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, _ObservedBackend
from legacy.xp_acq_control.elyse_agent.command_protocol import OPERATIONS
from legacy.xp_acq_control.elyse_agent.control_policy import command_capabilities
from legacy.xp_acq_control.elyse_agent.supervised_test import SUPERVISED_OPERATIONS


class Clock(object):
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now


def sample(fault=False):
    c3, c4 = [False] * 56, [False] * 64
    for index in (1, 4, 7, 10):
        c3[index] = True
    c4[19] = fault
    return dict(source="python_daqmx_acquisition", simulated=False,
                banks=dict(C3_DIO96_DI=dict(values=c3), C4_DIO96_DI=dict(values=c4)))


class Backend(object):
    operator_supervised_test = True
    operator_test_cold_attested = True
    startup_complete = True
    resource_count = 1
    control_profile = "general_only_test"
    stage_controls_verified = False
    focal_controls_verified = False
    ht_controls_verified = False
    counter_controls_verified = False
    counter_timing_controls_verified = False
    ht_voltage_controls_verified = False
    beamline_controls_verified = False
    ht_feedback_verified = False
    cooling_trip_verified = False

    def __init__(self):
        self.calls = []
        self.uncertain = False
        self.generation = 1

    def isolation_snapshot(self):
        return dict(ownership_uncertain=self.uncertain, worker_generation=self.generation)

    def general_start(self, cancel, operator_confirmed=False):
        self.calls.append("general")

    def execute_stage(self, operation, cancel, operator_confirmed=False):
        self.calls.append(operation)


class SupervisedRuntimeTests(unittest.TestCase):
    def make_runtime(self):
        clock, backend = Clock(), Backend()
        runtime = AcquisitionControlRuntime(lambda: backend, clock=clock, remote_enabled=True)
        wrapper = _ObservedBackend(backend, runtime)
        runtime._backend, runtime._state = wrapper, "RUNNING"
        runtime._ht_sequence_owner = wrapper
        runtime._ht_sequence_generation = backend.generation
        runtime._recovery_snapshot = lambda: dict(required=False, protection_active=True)
        self.read(runtime, clock)
        return runtime, clock, backend

    def read(self, runtime, clock, fault=False):
        runtime._latest = sample(fault)
        runtime._received_at = clock.now
        runtime._sequence += 1
        runtime._run_cooling_guard(runtime._latest)

    def general(self, runtime):
        runtime.general_start(operator_confirmed=True)
        runtime._pending = None  # Owner consumes queue before entering wrapper.
        runtime._backend.general_start(threading.Event(), operator_confirmed=True)
        runtime._state, runtime._operation = "RUNNING", None
        runtime._state_revision += 1

    def water(self, runtime, clock):
        for elapsed in (0., 1., 2.):
            clock.now = elapsed
            self.read(runtime, clock)

    def test_general_has_no_automatic_water_and_facts_stay_false(self):
        runtime, clock, backend = self.make_runtime()
        self.general(runtime)
        self.assertEqual(backend.calls, ["general"])
        value = runtime.snapshot()
        self.assertEqual(value["startup_phase"], "WAIT_OPERATOR_WATER")
        self.assertFalse(value["full_stop_commissioned"])
        self.assertFalse(value["general_cooling_ready"])
        self.assertTrue(value["operator_supervised_test"])
        self.assertTrue(value["operator_test_cold_attested"])
        self.assertTrue(all(value["stage_execution"][key] is False for key in
            ("commissioned", "ht_commissioned", "focal_commissioned", "counter_commissioned",
             "counter_timing_commissioned", "ht_voltage_commissioned", "beamline_commissioned")))
        self.read(runtime, clock)
        self.assertTrue(command_capabilities(runtime.snapshot())["cooling.start"]["enabled"])
        self.assertRaises(RuntimeError, runtime.stage_request, "chauffage.start", True)
        self.water(runtime, clock)
        self.assertTrue(runtime.snapshot()["general_cooling_ready"])
        for operation in ("chauffage.start", "prema.start", "focales.start", "relays_ht.start", "modulator.reset"):
            self.assertTrue(command_capabilities(runtime.snapshot())[operation]["enabled"], operation)
            self.assertTrue(runtime.stage_request(operation, operator_confirmed=True))
            runtime._state, runtime._pending, runtime._operation = "RUNNING", None, None
            runtime._received_at = clock.now
        self.assertEqual(backend.calls, ["general"])

    def test_cold_attestation_required_and_legacy_profile_cannot_enable_mode(self):
        for mode, cold in ((False, True), (True, False)):
            runtime, clock, backend = self.make_runtime()
            backend.operator_supervised_test, backend.operator_test_cold_attested = mode, cold
            self.assertRaises(RuntimeError, runtime.general_start, True)
            self.assertRaises(RuntimeError, runtime.stage_request, "focales.start", True)
            self.assertFalse(command_capabilities(runtime.snapshot())["modulator.general.start"]["enabled"])

    def test_stale_fault_generation_and_stop_invalidate_circulation(self):
        for failure in ("stale", "fault", "generation", "stop"):
            runtime, clock, backend = self.make_runtime()
            self.general(runtime)
            self.water(runtime, clock)
            if failure == "stale":
                clock.now += 2
                runtime._tick_cooling()
            elif failure == "fault":
                self.read(runtime, clock, fault=True)
            elif failure == "generation":
                backend.generation += 1
                self.read(runtime, clock)
            else:
                runtime.general_stop(operator_confirmed=True)
            self.assertFalse(runtime.snapshot()["general_cooling_ready"], failure)
            self.assertFalse(command_capabilities(runtime.snapshot())["chauffage.start"]["enabled"], failure)
            self.assertRaises(RuntimeError, runtime.stage_request, "chauffage.start", True)

    def test_no_energy_sync_or_beamline_permission_exemption(self):
        runtime, clock, backend = self.make_runtime()
        self.general(runtime)
        self.water(runtime, clock)
        capabilities = command_capabilities(runtime.snapshot())
        for operation in set(OPERATIONS) - SUPERVISED_OPERATIONS:
            self.assertFalse(capabilities[operation]["enabled"], operation)
        for operation in ("alimentation_ht.start", "modulator_impulse.start", "faraday_1.en_pulse"):
            self.assertRaises(RuntimeError, runtime.stage_request, operation, True)
        self.assertRaises(RuntimeError, runtime.set_ht_voltage, 1., True)

    def test_full_startup_and_known_owner_remain_required(self):
        for failure in ("startup", "owner", "recovery", "stale"):
            runtime, clock, backend = self.make_runtime()
            if failure == "startup":
                backend.startup_complete = False
            elif failure == "owner":
                backend.uncertain = None
            elif failure == "recovery":
                runtime._recovery_snapshot = lambda: dict(required=True, protection_active=True, reason="test")
            else:
                clock.now = 2.
            self.assertRaises(RuntimeError, runtime.general_start, True)
            self.assertFalse(command_capabilities(runtime.snapshot())["modulator.general.start"]["enabled"], failure)

    def test_two_minute_alarm_attempts_general_stop_without_commissioning(self):
        runtime, clock, backend = self.make_runtime()
        self.general(runtime)
        self.water(runtime, clock)
        self.read(runtime, clock, fault=True)
        self.assertFalse(runtime._stop_qualified())
        clock.now = 121.9
        runtime._tick_cooling()
        self.assertIsNone(runtime._pending)
        clock.now = 122.
        runtime._tick_cooling()
        self.assertEqual(runtime._pending, "general_stop")
        self.assertEqual(runtime.cooling.snapshot()["stop_state"], "REQUESTED")

    def test_stop_failure_is_reported_and_journal_alarm_blocks_start(self):
        runtime, clock, backend = self.make_runtime()
        self.general(runtime)
        self.water(runtime, clock)
        self.read(runtime, clock, fault=True)
        def fail_stop(operator_confirmed=False):
            raise RuntimeError("injected stop admission failure")
        runtime.general_stop = fail_stop
        clock.now = 122.
        runtime._tick_cooling()
        self.assertEqual(runtime.cooling.snapshot()["stop_state"], "FAILED")
        self.assertIn("injected stop admission failure", runtime.cooling.snapshot()["stop_error"])
        self.assertRaises(RuntimeError, runtime._start_permit, True)

    def test_queued_start_rechecks_freshness_before_any_backend_write(self):
        runtime, clock, backend = self.make_runtime()
        runtime.general_start(operator_confirmed=True)
        runtime._pending = None
        clock.now = 2.
        self.assertRaises(RuntimeError, runtime._backend.general_start, threading.Event(), True)
        self.assertEqual(backend.calls, [])
        runtime, clock, backend = self.make_runtime()
        self.general(runtime)
        self.water(runtime, clock)
        runtime.stage_request("chauffage.start", operator_confirmed=True)
        runtime._pending = None
        clock.now += 2.
        self.assertRaises(RuntimeError, runtime._backend.execute_stage,
                          "chauffage.start", threading.Event(), True)
        self.assertEqual(backend.calls, ["general"])

    def test_current_journal_failure_blocks_supervised_general(self):
        runtime, clock, backend = self.make_runtime()
        alarm = runtime.cooling.snapshot()
        alarm["journal_storage_error"] = "injected journal failure"
        runtime.cooling.snapshot = lambda: alarm
        self.assertRaises(RuntimeError, runtime.general_start, True)
        self.assertEqual(backend.calls, [])

    def test_broker_still_requires_current_session_and_lease(self):
        runtime, clock, backend = self.make_runtime()
        identity = runtime.snapshot()
        request = dict(command_id="a" * 32, session_id=identity["session_id"],
            expected_revision=identity["state_revision"], operation="modulator.general.start",
            operator_confirmed=True, value=None)
        self.assertRaises(RuntimeError, runtime.broker.submit, request, None)
        lease = runtime.broker.snapshot(issue_lease=True)["lease"]
        request["session_id"] = "f" * 32
        self.assertRaises(RuntimeError, runtime.broker.submit, request, lease)
        self.assertIsNone(runtime._pending)


if __name__ == "__main__":
    unittest.main()
