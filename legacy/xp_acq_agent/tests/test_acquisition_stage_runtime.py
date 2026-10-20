"""Stage scheduling and recovery on fake owners only; Python 3.4 compatible."""
import copy
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution import (
    SUPPORTED_OPERATIONS, StageExecutionCancelled,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_gui import load_configuration, AcquisitionWindow
from legacy.xp_acq_agent.tests.test_acquisition_runtime import FakeBackend, wait_state


class StageBackend(FakeBackend):
    def __init__(self):
        FakeBackend.__init__(self)
        self.stage_controls_verified = True
        self._stage_simulated = False  # Fake NI owner, not a synthetic Demo source.
        self.cooling_trip_verified = False
        self.ht_controls_verified = True  # Fake-only explicit HT qualification.
        self.stage_entered = threading.Event()
        self.stage_release = threading.Event()
        self.stage_release.set()
        self.stage_calls = []
        self.trip_calls = []
        self.read_threads = []
        self.fail_stage = False
        self.fail_trip = False
        self.inputs_trip = False
        self.after_stage_read = None
        self.after_stage_release = None

    def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        self.stage_calls.append((operation, threading.current_thread().ident, operator_confirmed))
        self.stage_entered.set()
        while not self.stage_release.wait(.002):
            if cancel.is_set() and not operation.endswith(".stop"):
                raise StageExecutionCancelled(dict(operation=operation, status="CANCELLED"))
        if self.fail_stage:
            raise RuntimeError("synthetic stage output failure")
        if cancel.is_set():
            raise RuntimeError("stale cancellation was not cleared by owner")
        self.procedure = dict(name=operation, hardware_acknowledged=False)

    def read_snapshot(self, cancel):
        self.read_threads.append(threading.current_thread().ident)
        if self.after_stage_read is not None and self.stage_calls:
            self.after_stage_read.set()
            self.after_stage_release.wait(2)
        value = FakeBackend.read_snapshot(self, cancel)
        c4, c3 = [False] * 64, [False] * 56
        c4[19] = self.inputs_trip
        value["banks"] = {"C4_DIO96_DI": {"values": c4}, "C3_DIO96_DI": {"values": c3}}
        return value

    def execute_cooling_guard(self, snapshot, cancel):
        self.trip_calls.append((copy.deepcopy(snapshot), threading.current_thread().ident))
        self.inputs_trip = False
        if self.fail_trip:
            raise RuntimeError("synthetic cooling output failure")
        return dict(status="COMPLETED", hardware_acknowledged=False)

    def general_stop(self, operator_confirmed=False):
        self.procedure = dict(name="general.stop", hardware_acknowledged=False)


class StageRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.backend = StageBackend()
        self.runtime = AcquisitionRuntime(lambda: self.backend, period=.02)
        self.runtime.start()

    def tearDown(self):
        self.backend.fail_stage = self.backend.fail_trip = False
        self.backend.stage_release.set()
        if self.backend.after_stage_release is not None:
            self.backend.after_stage_release.set()
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(3))

    def initialize(self):
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "RUNNING")

    def wait_calls(self, collection, count=1):
        deadline = time.monotonic() + 2
        while len(collection) < count and time.monotonic() < deadline:
            time.sleep(.002)
        self.assertGreaterEqual(len(collection), count)

    def test_cold_false_newval_and_invalid_requests_have_no_effects(self):
        self.assertFalse(self.runtime.stage_request("chauffage.start", True, False))
        for operation in ("focales.start", "arbitrary"):
            with self.assertRaises(ValueError):
                self.runtime.stage_request(operation, True)
        with self.assertRaises(ValueError):
            self.runtime.stage_request("chauffage.start")
        with self.assertRaises(ValueError):
            self.runtime.stage_request("chauffage.start", True, 1)
        with self.assertRaises(RuntimeError):
            self.runtime.stage_request("chauffage.start", True)
        self.assertEqual(self.runtime.snapshot()["state"], "IDLE")
        self.assertEqual(self.backend.stage_calls, [])

    def test_default_or_general_only_gate_cannot_be_promoted_by_runtime(self):
        self.initialize()
        self.backend.stage_controls_verified = False
        with self.assertRaises(RuntimeError):
            self.runtime.stage_request("chauffage.start", True)
        self.backend.stage_controls_verified = True
        self.backend.control_profile = "general_only_test"
        with self.assertRaises(RuntimeError):
            self.runtime.stage_request("chauffage.start", True)
        self.assertEqual(self.backend.stage_calls, [])
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])

    def test_all_twelve_operations_run_on_the_existing_ni_owner(self):
        self.initialize()
        for number, operation in enumerate(SUPPORTED_OPERATIONS, 1):
            self.assertTrue(self.runtime.stage_request(operation, True))
            self.wait_calls(self.backend.stage_calls, number)
            wait_state(self.runtime, "RUNNING")
        self.assertTrue(all(row[1] == self.runtime._thread.ident and row[2]
                            for row in self.backend.stage_calls))
        self.assertEqual(self.backend.close_calls, 0)
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])

    def test_ht_gate_is_independent_and_rejection_cannot_change_release_state(self):
        self.initialize()
        self.backend.ht_controls_verified = False
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset"):
            self.assertFalse(self.runtime.stage_request(operation, True, False))
            with self.assertRaises(RuntimeError):
                self.runtime.stage_request(operation, True)
        state = self.runtime.snapshot()
        self.assertFalse(state["ht_supply_stop_required"])
        self.assertFalse(state["general_stop_required"])
        self.assertFalse(state["stage_execution"]["ht_commissioned"])
        self.assertEqual(self.backend.stage_calls, [])

    def test_standalone_ht_stop_and_legacy_general_stop_do_not_authorize_release(self):
        self.initialize()
        self.backend.control_profile = "legacy_full"
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset"):
            self.runtime.stage_request(operation, True)
            wait_state(self.runtime, "RUNNING")
            self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        state = self.runtime.snapshot()
        self.assertTrue(state["ht_supply_stop_required"])
        self.assertTrue(state["general_stop_required"])
        for action in (self.runtime.deinitialize, self.runtime.request_shutdown):
            with self.assertRaises(RuntimeError):
                action()
        self.assertEqual(self.backend.close_calls, 0)

    def test_only_qualified_extended_general_stop_clears_ht_release_requirement(self):
        self.initialize()
        self.backend.control_profile = "extended_ht_stop"
        self.runtime.stage_request("alimentation_ht.start", True)
        wait_state(self.runtime, "RUNNING")
        self.backend.ht_feedback_verified = False
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        # Fake callback represents a successfully completed qualified extension;
        # real backend must perform fresh zero/OFF and counter-stop checks.
        self.backend.ht_feedback_verified = True
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertFalse(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])

    def test_failed_ht_command_retains_requirement_until_explicit_local_off(self):
        self.initialize()
        self.backend.fail_stage = True
        self.runtime.stage_request("alimentation_ht.start", True)
        wait_state(self.runtime, "FAULT")
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.runtime.deinitialize(electrical_off_confirmed=True)
        wait_state(self.runtime, "IDLE")
        self.assertFalse(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertEqual(self.backend.close_calls, 1)

    def test_failed_qualified_extended_stop_never_clears_ht_requirement(self):
        self.initialize()
        self.backend.control_profile = "extended_ht_stop"
        self.backend.ht_feedback_verified = True
        self.runtime.stage_request("alimentation_ht.start", True)
        wait_state(self.runtime, "RUNNING")
        self.backend.general_stop = Mock(side_effect=RuntimeError("synthetic HT zero/OFF check failure"))
        self.runtime.general_stop(True)
        wait_state(self.runtime, "FAULT")
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])
        self.assertEqual(self.backend.close_calls, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()

    def test_legacy_general_interrupts_ht_start_but_does_not_clear_ht_requirement(self):
        self.initialize()
        self.backend.control_profile = "legacy_full"
        self.backend.stage_release.clear()
        self.runtime.stage_request("alimentation_ht.start", True)
        self.assertTrue(self.backend.stage_entered.wait(1))
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertEqual(self.backend.close_calls, 0)

    def test_partial_failure_keeps_owner_and_accepts_only_explicit_stop_recovery(self):
        self.initialize()
        self.backend.fail_stage = True
        self.runtime.stage_request("chauffage.start", True)
        wait_state(self.runtime, "FAULT")
        self.assertEqual(self.backend.close_calls, 0)
        self.assertEqual(self.runtime.snapshot()["resource_count"], 2)
        for action in (self.runtime.deinitialize, self.runtime.request_shutdown):
            with self.assertRaises(RuntimeError):
                action()
        with self.assertRaises(RuntimeError):
            self.runtime.stage_request("prema.start", True)
        self.backend.fail_stage = False
        self.runtime._cancel.set()  # Retained cancellation from an earlier failed stop.
        self.runtime.stage_request("chauffage.stop", True)
        self.wait_calls(self.backend.stage_calls, 2)
        wait_state(self.runtime, "RUNNING")
        self.assertFalse(self.runtime._cancel.is_set())
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])

    def test_general_stop_interrupts_start_without_releasing_or_reopening_owner(self):
        self.initialize()
        self.backend.stage_release.clear()
        self.runtime.stage_request("prema.start", True)
        self.assertTrue(self.backend.stage_entered.wait(1))
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.backend.close_calls, 0)
        self.assertEqual(self.backend.procedure["name"], "general.stop")
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])

    def test_stop_cannot_be_cancelled_by_close_or_another_procedure(self):
        self.initialize()
        self.backend.stage_release.clear()
        self.runtime.stage_request("prema.stop", True)
        self.assertTrue(self.backend.stage_entered.wait(1))
        try:
            for action in (self.runtime.deinitialize, self.runtime.request_shutdown):
                with self.assertRaises(RuntimeError):
                    action(electrical_off_confirmed=True)
            with self.assertRaises(RuntimeError):
                self.runtime.general_stop(True)
            with self.assertRaises(RuntimeError):
                self.runtime.stage_request("chauffage.stop", True)
            self.assertFalse(self.runtime._cancel.is_set())
        finally:
            self.backend.stage_release.set()
        wait_state(self.runtime, "RUNNING")

    def test_confirmed_close_queued_during_failed_start_still_shuts_down(self):
        self.initialize()
        self.backend.stage_release.clear()
        self.runtime.stage_request("chauffage.start", True)
        self.assertTrue(self.backend.stage_entered.wait(1))
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(2))
        self.assertEqual(self.runtime.snapshot()["state"], "STOPPED")
        self.assertEqual(self.backend.close_calls, 1)

    def test_precommand_measurement_stays_stale_until_a_new_owner_read(self):
        self.initialize()
        self.backend.stage_release.clear()
        self.backend.after_stage_read, self.backend.after_stage_release = threading.Event(), threading.Event()
        self.runtime.stage_request("prema.start", True)
        self.assertTrue(self.backend.stage_entered.wait(1))
        self.assertTrue(self.runtime.snapshot()["stale"])
        self.assertIsNone(self.runtime.snapshot()["age_seconds"])
        self.backend.stage_release.set()
        self.assertTrue(self.backend.after_stage_read.wait(1))
        self.assertEqual(self.runtime.snapshot()["state"], "RUNNING")
        self.assertTrue(self.runtime.snapshot()["stale"])
        self.backend.after_stage_release.set()

    def test_enabled_cooling_trip_consumes_current_raw_inputs_on_same_owner(self):
        self.backend.cooling_trip_verified = self.backend.inputs_trip = True
        self.initialize()
        self.wait_calls(self.backend.trip_calls)
        wait_state(self.runtime, "RUNNING")
        snapshot, owner = self.backend.trip_calls[0]
        self.assertTrue(snapshot["banks"]["C4_DIO96_DI"]["values"][19])
        self.assertEqual(owner, self.runtime._thread.ident)
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])
        self.assertEqual(self.backend.stage_calls, [])

    def test_disabled_guard_and_general_only_do_not_change_shutdown_state(self):
        self.backend.cooling_trip_verified = False
        self.backend.inputs_trip = True
        self.initialize()
        self.wait_calls(self.backend.read_threads)
        self.assertFalse(self.backend.trip_calls)
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])
        self.backend.cooling_trip_verified = True
        self.backend.control_profile = "general_only_test"
        previous = len(self.backend.read_threads)
        self.wait_calls(self.backend.read_threads, previous + 2)
        self.assertFalse(self.backend.trip_calls)
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])

    def test_cooling_trip_failure_retains_faulted_owner_not_a_fake_fresh_read(self):
        self.backend.cooling_trip_verified = self.backend.inputs_trip = self.backend.fail_trip = True
        self.runtime.initialize(startup_confirmed=True)
        wait_state(self.runtime, "FAULT")
        self.assertIn("synthetic cooling", self.runtime.snapshot()["error"])
        self.assertTrue(self.runtime.snapshot()["stale"])
        self.assertEqual(self.backend.close_calls, 0)
        self.assertEqual(self.runtime.snapshot()["resource_count"], 2)

    def test_true_raw_expression_never_executes_on_explicit_demo_source(self):
        self.backend._stage_simulated = True
        self.backend.cooling_trip_verified = self.backend.inputs_trip = True
        self.initialize()
        self.wait_calls(self.backend.read_threads, 2)
        self.assertFalse(self.backend.trip_calls)
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])


class StageConfigurationTests(unittest.TestCase):
    def config(self, directory, **flags):
        path = os.path.join(directory, "config.json")
        key = os.path.join(directory, "dummy-test.key")
        with open(key, "wb") as stream:
            stream.write(b"fake-only-acquisition-stage-config-key-000000")
        value = dict(bind_host="127.0.0.1", port=8771, key_file=key,
                     period_seconds=.2, read_timeout_seconds=.5)
        value.update(flags)
        with open(path, "w") as stream:
            json.dump(value, stream)
        return path

    def test_legacy_configuration_does_not_enable_any_stage_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            value, unused_key = load_configuration(self.config(directory))
        self.assertIs(value.get("stage_controls_verified", False), False)
        self.assertIs(value.get("cooling_trip_verified", False), False)
        self.assertIs(value.get("ht_controls_verified", False), False)

    def test_explicit_separate_boolean_gates_are_accepted_without_creating_an_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            value, unused_key = load_configuration(self.config(
                directory, stage_controls_verified=True, cooling_trip_verified=False,
                ht_controls_verified=True))
        self.assertIs(value["stage_controls_verified"], True)
        self.assertIs(value["cooling_trip_verified"], False)
        self.assertIs(value["ht_controls_verified"], True)

    def test_malformed_flag_values_are_not_treated_as_commissioning(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("stage_controls_verified", "cooling_trip_verified", "ht_controls_verified"):
                for invalid in ("true", 1, None, []):
                    with self.assertRaises(ValueError):
                        load_configuration(self.config(directory, **{name: invalid}))

    def test_gui_physical_off_prompt_includes_independent_ht_requirement(self):
        window = object.__new__(AcquisitionWindow)
        window.runtime, window.messagebox, window.root = Mock(), Mock(), object()
        window.runtime.snapshot.return_value = dict(general_stop_required=False, ht_supply_stop_required=True)
        window.messagebox.askyesno.return_value = False
        with self.assertRaises(RuntimeError):
            window.confirm_local_off()
        self.assertIn("HT supply stop remains unconfirmed", window.messagebox.askyesno.call_args[0][1])
        window.messagebox.askyesno.return_value = True
        self.assertTrue(window.confirm_local_off())


if __name__ == "__main__":
    unittest.main()
