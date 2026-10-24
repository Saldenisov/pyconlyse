"""Driver-free named experiment admission and same-owner software ordering.

No server or child process is opened. Synthetic callbacks are software effects,
never evidence of qualified water, HT, Faraday position or mirror readback.
"""
import copy
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime
from legacy.xp_acq_control.elyse_agent.command_protocol import OPERATIONS, validate_request
from legacy.xp_acq_control.elyse_agent.control_policy import (
    BEAMLINE_OPERATIONS, command_capabilities, require_command, require_ht_value,
)
from legacy.xp_acq_control.elyse_agent.isolated_backend import CACHED_ATTRIBUTES
from legacy.xp_acq_control.elyse_agent.isolated_backend import remote_error
from legacy.xp_acq_control.elyse_agent.isolated_worker import _attributes
from legacy.xp_acq_control.elyse_agent.acquisition_beamline import BeamlineExecutionError


def sequence(ready=False):
    return dict(owner_current=True, command_known=True, current_command_kv=6.5,
                supply_sequence_completed=ready, pulses_sequence_completed=ready,
                hardware_acknowledged=False)


def sample():
    return dict(source="python_daqmx_acquisition", simulated=False, banks={})


def ready_state():
    return dict(state="RUNNING", stale=False, age_seconds=.1, error="", resource_count=1,
        remote_setpoints_enabled=True, general_stop_required=False,
        recovery=dict(required=False, protection_active=True), latest=sample(),
        stage_execution=dict(commissioned=True, beamline_commissioned=True,
            ht_commissioned=True, focal_commissioned=True, counter_commissioned=True,
            ht_voltage_commissioned=True), full_stop_commissioned=True,
        general_cooling_ready=True, cooling_permit_current=True, ht_sequence_state=sequence())


class FakeCards(object):
    control_profile = "legacy_full"
    stage_controls_verified = beamline_controls_verified = True
    ht_controls_verified = counter_controls_verified = ht_voltage_controls_verified = True
    focal_controls_verified = cooling_trip_verified = outer_stop_verified = False
    procedure = None

    def __init__(self):
        self.active, self.current, self.supply, self.pulses = False, 6.5, False, False
        self.calls, self.eps, self.dps = [], [False] * 77, [False] * 29
        self.fail, self.uncertain = None, False
        self.generation = "generation-one"

    @property
    def resource_count(self):
        return int(self.active)

    @property
    def ht_sequence_state(self):
        return dict(command_known=self.active and not self.uncertain,
            current_command_kv=self.current, supply_sequence_completed=self.eps[45],
            pulses_sequence_completed=self.eps[52], hardware_acknowledged=False)

    def initialize(self, cancel, startup_confirmed=False):
        self.active = True

    def read_snapshot(self, cancel):
        return sample()

    def execute_stage(self, operation, cancel, operator_confirmed=False):
        self.calls.append((operation, threading.current_thread().ident))
        if self.fail == operation:
            raise RuntimeError("Synthetic stage failure after possible effect")
        if operation == "alimentation_ht.start":
            self.eps[45] = True
        elif operation == "alimentation_ht.stop":
            self.eps[45] = False

    def execute_impulsion(self, operation, cancel, operator_confirmed=False):
        self.calls.append((operation, threading.current_thread().ident))
        if self.fail == operation:
            raise RuntimeError("Synthetic impulse failure")
        self.eps[52] = operation.endswith(".start")

    def set_ht_voltage(self, value, cancel, operator_confirmed=False):
        self.calls.append(("ht_voltage.set", value, threading.current_thread().ident))
        self.current = value

    def general_stop(self, operator_confirmed=False):
        self.calls.append(("general.stop", threading.current_thread().ident))

    def close(self):
        self.active = False


def wait_running(runtime, state="RUNNING"):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        view = runtime.snapshot()
        if view["state"] == state and (state != "RUNNING" or view["stale"] is False):
            return view
        time.sleep(.002)
    raise AssertionError("Runtime did not reach " + state + ": " + str(runtime.snapshot()))


class ExperimentPolicyTests(unittest.TestCase):
    def test_only_four_explicit_beamline_names_no_open_or_hors_alias(self):
        self.assertEqual(set(BEAMLINE_OPERATIONS), {
            "faraday_1.en_pulse", "faraday_3.en_pulse", "laser_mirror.en_pulse", "laser_mirror.hors_pulse"})
        self.assertEqual(len(OPERATIONS), 23)
        for name in BEAMLINE_OPERATIONS:
            request = dict(command_id="a" * 32, session_id="b" * 32, expected_revision=1,
                           operation=name, operator_confirmed=True, value=None)
            self.assertEqual(validate_request(request)["operation"], name)
            request["value"] = 1
            with self.assertRaises(ValueError):
                validate_request(request)
        for name in ("faraday_1.open", "faraday_1.hors_pulse", "faraday_3.hors_pulse",
                     "acquisition.initialize", "server.stop"):
            self.assertNotIn(name, OPERATIONS)

    def test_motion_needs_fresh_running_owner_cooling_shutdown_and_separate_gate(self):
        baseline = ready_state()
        for name in BEAMLINE_OPERATIONS:
            self.assertTrue(command_capabilities(baseline)[name]["enabled"])
            variants = [dict(state="FAULT"), dict(state="EXECUTING"), dict(stale=True),
                        dict(age_seconds=2), dict(full_stop_commissioned=False),
                        dict(general_cooling_ready=False), dict(cooling_permit_current=False)]
            for fields in variants:
                value = copy.deepcopy(baseline)
                value.update(fields)
                self.assertFalse(command_capabilities(value)[name]["enabled"], (name, fields))
            value = copy.deepcopy(baseline)
            value["stage_execution"]["beamline_commissioned"] = False
            self.assertEqual(command_capabilities(value)[name]["reason"], "BEAMLINE_CONTROLS_NOT_COMMISSIONED")

    def test_ht_static_capability_keeps_decrease_dynamic_gate_blocks_increase(self):
        value = ready_state()
        self.assertTrue(command_capabilities(value)["ht_voltage.set"]["enabled"])
        require_command(value, "ht_voltage.set", 6.0)
        require_command(value, "ht_voltage.set", 6.5)
        with self.assertRaises(RuntimeError):
            require_command(value, "ht_voltage.set", 6.6)
        value["ht_sequence_state"] = sequence(True)
        require_command(value, "ht_voltage.set", 6.6)
        for field in ("owner_current", "command_known", "supply_sequence_completed", "pulses_sequence_completed"):
            bad = sequence(True)
            bad[field] = False
            with self.assertRaises(RuntimeError):
                require_ht_value(bad, 6.6)
        for bad in (None, {}, dict(sequence(True), current_command_kv=float("nan"))):
            with self.assertRaises(RuntimeError):
                require_ht_value(bad, 6.0)

    def test_stops_are_not_conditioned_on_fresh_inputs_or_ht_start_sequences(self):
        value = ready_state()
        value.update(state="FAULT", stale=True, age_seconds=100, error="input failure")
        value["ht_sequence_state"] = {}
        caps = command_capabilities(value)
        for name in ("modulator.general.stop", "alimentation_ht.stop", "modulator_impulse.stop"):
            self.assertTrue(caps[name]["enabled"], (name, caps[name]))

    def test_commissioning_and_sequence_state_cross_isolation_as_ram_attributes(self):
        self.assertIn("beamline_controls_verified", CACHED_ATTRIBUTES)
        self.assertIn("ht_sequence_state", CACHED_ATTRIBUTES)
        cards = FakeCards()
        cards.active = True
        projected = _attributes(cards)
        self.assertIs(projected["beamline_controls_verified"], True)
        self.assertTrue(projected["ht_sequence_state"]["command_known"])
        self.assertFalse(projected["ht_sequence_state"]["supply_sequence_completed"])
        report = dict(operation="faraday_1.en_pulse", status="FAILED", pending_release=True)
        error = remote_error(dict(type="BeamlineExecutionError", message="failed", report=report))
        self.assertIsInstance(error, BeamlineExecutionError)
        self.assertEqual(error.report, report)


class ExperimentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.cards = FakeCards()
        self.runtime = AcquisitionRuntime(lambda: self.cards, period=.02)
        self.runtime.start()
        self.runtime.initialize(True)
        wait_running(self.runtime)

    def tearDown(self):
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(2))

    def start_sequences(self):
        for operation in ("alimentation_ht.start", "modulator_impulse.start"):
            self.runtime.stage_request(operation, True)
            wait_running(self.runtime)

    def test_ht_before_sequence_rejected_after_both_completions_scalar_is_transferred(self):
        with self.assertRaises(RuntimeError):
            self.runtime.set_ht_voltage(7.0, True)
        self.runtime.stage_request("alimentation_ht.start", True)
        wait_running(self.runtime)
        with self.assertRaises(RuntimeError):
            self.runtime.set_ht_voltage(7.0, True)
        self.runtime.stage_request("modulator_impulse.start", True)
        wait_running(self.runtime)
        self.runtime.set_ht_voltage(7.0, True)
        wait_running(self.runtime)
        sets = [row for row in self.cards.calls if row[0] == "ht_voltage.set"]
        self.assertEqual(len(sets), 1)  # One scalar commit, never an invented ramp.
        self.assertEqual(sets[0][1], 7.0)
        self.assertNotEqual(sets[0][2], threading.current_thread().ident)
        self.assertFalse(self.runtime.snapshot()["ht_sequence_state"]["hardware_acknowledged"])

    def test_forged_eps_without_current_runtime_completions_does_not_admit_increase(self):
        self.cards.eps[45] = self.cards.eps[52] = True
        with self.assertRaises(RuntimeError):
            self.runtime.set_ht_voltage(7.0, True)
        self.runtime.set_ht_voltage(6.0, True)
        wait_running(self.runtime)
        self.assertEqual(self.cards.current, 6.0)

    def test_stale_missing_or_changed_owner_cannot_authorize_increase(self):
        self.start_sequences()
        with self.runtime._lock:
            self.runtime._received_at = self.runtime._clock() - 3
            with self.assertRaises(RuntimeError):
                self.runtime.set_ht_voltage(7.0, True)
            self.runtime._received_at = self.runtime._clock()
            self.runtime._ht_sequence_owner = object()
            with self.assertRaises(RuntimeError):
                self.runtime.set_ht_voltage(7.0, True)

    def test_generation_change_or_ambiguous_command_cannot_reuse_eps(self):
        self.start_sequences()
        with self.runtime._lock:
            self.cards.isolation_snapshot = lambda: dict(
                ownership_uncertain=False, worker_generation=self.cards.generation)
            self.runtime._ht_sequence_generation = self.cards.generation
            self.cards.generation = "new-generation"
            with self.assertRaises(RuntimeError):
                self.runtime.set_ht_voltage(7.0, True)
            self.cards.generation = self.runtime._ht_sequence_generation
            self.cards.uncertain = True
            for value in (6.0, 7.0):
                with self.assertRaises(RuntimeError):
                    self.runtime.set_ht_voltage(value, True)

    def test_queued_increase_rechecks_freshness_before_owner_callback(self):
        self.start_sequences()
        with self.runtime._lock:
            self.runtime.set_ht_voltage(7.0, True)
            # Deterministic simulated admission-to-execution delay, no sleep.
            self.runtime._ht_command_observation_at = self.runtime._clock() - 3
        wait_running(self.runtime, "FAULT")
        self.assertFalse(any(row[0] == "ht_voltage.set" for row in self.cards.calls))
        self.assertEqual(self.runtime.snapshot()["resource_count"], 1)

    def test_stop_supersedes_queued_increase_without_output_and_clears_proof(self):
        self.start_sequences()
        with self.runtime._lock:
            self.runtime.set_ht_voltage(7.0, True)
            self.runtime.general_stop(True)
        wait_running(self.runtime)
        self.assertFalse(any(row[0] == "ht_voltage.set" for row in self.cards.calls))
        self.assertFalse(self.runtime.snapshot()["ht_sequence_state"]["supply_sequence_completed"])

    def test_direct_motion_refuses_stale_or_simulated_input_before_queueing(self):
        with self.runtime._lock:
            self.runtime._received_at = self.runtime._clock() - 2
            with self.assertRaises(RuntimeError):
                self.runtime.stage_request(BEAMLINE_OPERATIONS[0], True)
            self.runtime._received_at = self.runtime._clock()
            self.runtime._latest["simulated"] = True
            with self.assertRaises(RuntimeError):
                self.runtime.stage_request(BEAMLINE_OPERATIONS[0], True)
            self.assertEqual(self.cards.calls, [])

    def test_all_beamline_pulses_route_on_one_owner_without_dps_synthesis(self):
        before = list(self.cards.dps)
        for operation in BEAMLINE_OPERATIONS:
            self.runtime.stage_request(operation, True)
            wait_running(self.runtime)
        self.assertEqual([row[0] for row in self.cards.calls], list(BEAMLINE_OPERATIONS))
        self.assertEqual(len(set(row[1] for row in self.cards.calls)), 1)
        self.assertEqual(self.cards.dps, before)
        self.assertTrue(self.runtime.snapshot()["stage_execution"]["beamline_commissioned"])

    def test_motion_failure_retains_owner_and_blocks_more_motion_in_fault(self):
        self.cards.fail = BEAMLINE_OPERATIONS[0]
        self.runtime.stage_request(BEAMLINE_OPERATIONS[0], True)
        wait_running(self.runtime, "FAULT")
        self.assertEqual(self.runtime.snapshot()["resource_count"], 1)
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])
        with self.assertRaises(RuntimeError):
            self.runtime.stage_request(BEAMLINE_OPERATIONS[1], True)
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()

    def test_general_stop_invalidates_old_start_completions_without_freshness_requirement(self):
        self.start_sequences()
        with self.runtime._lock:
            self.runtime._received_at = self.runtime._clock() - 100
            self.runtime.general_stop(True)
            state = self.runtime._ht_sequence_snapshot()
            self.assertFalse(state["supply_sequence_completed"])
            self.assertFalse(state["pulses_sequence_completed"])
        wait_running(self.runtime)
        with self.assertRaises(RuntimeError):
            self.runtime.set_ht_voltage(7.0, True)


class RemoteBeamlineDispatchTests(unittest.TestCase):
    def test_all_pulses_take_guarded_stage_path_not_raw_digital_path(self):
        for operation in BEAMLINE_OPERATIONS:
            runtime = AcquisitionControlRuntime(lambda: None)
            calls = []
            runtime.snapshot = ready_state
            runtime._start_permit = lambda: calls.append("permit")
            runtime.stage_request = lambda name, operator_confirmed=False: calls.append((name, operator_confirmed))
            runtime.dispatch_remote(operation, None)
            self.assertEqual(calls, ["permit", (operation, True)])


if __name__ == "__main__":
    unittest.main()
