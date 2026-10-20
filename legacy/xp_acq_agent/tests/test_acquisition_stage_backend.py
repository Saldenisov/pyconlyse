"""Offline real CardBackend methods with an injected fake NI owner only."""
import copy
import json
import threading
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution import StageExecutionError
from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import GeneralStopError
from legacy.xp_acq_agent.elyse_agent.chroma_focal_stop import ChromaFocalStop
from legacy.xp_acq_agent.elyse_agent.hardware_plan import digital_startup_image


class FastCancel(object):
    def __init__(self):
        self.cancelled = False
        self.waits = []

    def is_set(self):
        return self.cancelled

    def wait(self, seconds):
        self.waits.append(seconds)
        return self.cancelled


class FailedWait(FastCancel):
    def wait(self, seconds):
        raise RuntimeError("synthetic wait failure after asserted pulse")


class FakeFocalCommand(object):
    """No process, DLL, COM port or NI call exists in this test adapter."""
    simulated = True

    def __init__(self, resources_verified=True):
        self.resources_verified = resources_verified
        self.calls = []
        self.blocked = False
        self.ready_error = None
        self.execute_callback = None

    def ensure_ready(self):
        self.calls.append(("ready",))
        if self.ready_error is not None:
            raise self.ready_error
        self.ensure_quiescent()

    def ensure_quiescent(self):
        self.calls.append(("quiet",))
        if self.blocked:
            raise RuntimeError("synthetic ON worker remains unconfirmed alive")

    def execute(self, output_enabled, cancelled):
        self.calls.append(("execute", output_enabled))
        if self.execute_callback is not None:
            return self.execute_callback(output_enabled, cancelled)
        return dict(simulated=True, output_enabled=output_enabled, hardware_acknowledged=False)

    def snapshot(self):
        return dict(simulated=True, pending_worker_count=1 if self.blocked else 0,
                    hardware_acknowledged=False, physical_output_state="UNKNOWN")


def fake_owner():
    owner = Mock()
    owner.tasks = {}
    for name, size in (("C1_NI6071E_AI", 64), ("C2_NI6071E_AI", 64),
                       ("C11_NI6220_AI", 16), ("C3_DIO96_DI", 56),
                       ("C4_DIO96_DI", 64), ("C5_DIO96_DI", 56)):
        task = Mock()
        task.read.return_value = [False] * size
        owner.tasks[name] = task
    owner.read_analog_means.side_effect = lambda name, **_kw: [0.0] * (
        16 if name == "C11_NI6220_AI" else 64)
    owner.start_legacy_counters.return_value = [0, 1, 2, 5, 6, 7]
    owner.write_initial_images.return_value = dict(
        digital=digital_startup_image(), analog_volts={})
    return owner


class AcquisitionStageBackendTests(unittest.TestCase):
    def backend(self, **kwargs):
        owner = fake_owner()
        backend = CardBackend(Mock(return_value=owner), **kwargs)
        backend.initialize(threading.Event(), startup_confirmed=True)
        return backend, owner

    def test_default_gate_blocks_effects_even_before_initialization(self):
        factory = Mock()
        backend = CardBackend(factory)
        for operation in ("chauffage.start", "chauffage.stop", "modulator.reset"):
            with self.assertRaisesRegex(RuntimeError, "not commissioned"):
                backend.execute_stage(operation, FastCancel(), operator_confirmed=True)
        factory.assert_not_called()
        self.assertEqual(backend.resource_count, 0)

    def test_closed_gate_does_not_write_existing_owner_or_status(self):
        backend, owner = self.backend()
        before = backend.read_snapshot(FastCancel())
        with self.assertRaises(RuntimeError):
            backend.execute_stage("prema.start", FastCancel(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(before["stage_state"], backend.read_snapshot(FastCancel())["stage_state"])

    def test_explicit_confirmation_initialization_and_profile_are_separate_gates(self):
        backend = CardBackend(stage_controls_verified=True)
        with self.assertRaises(ValueError):
            backend.execute_stage("cooling.start", FastCancel())
        with self.assertRaisesRegex(RuntimeError, "initialized"):
            backend.execute_stage("cooling.start", FastCancel(), operator_confirmed=True)
        backend, owner = self.backend(stage_controls_verified=True, control_profile="general_only_test")
        with self.assertRaisesRegex(RuntimeError, "General-only"):
            backend.execute_stage("cooling.stop", FastCancel(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()

    def test_flags_reject_truthy_integers_or_text_without_factory_calls(self):
        for flags in ({"stage_controls_verified": 1}, {"cooling_trip_verified": "yes"}):
            factory = Mock()
            with self.assertRaises(ValueError):
                CardBackend(factory, **flags)
            factory.assert_not_called()

    def test_all_nine_exact_digital_field_paths_preserve_unrelated_fields(self):
        cases = {
            "cooling.start": ("C3_DIO96_DO", [(0, True), (0, False), (3, True), (3, False),
                                                     (0, True), (0, False), (2, True), (2, False)]),
            "cooling.stop": ("C3_DIO96_DO", [(1, False), (1, True), (4, False), (4, True)]),
            "chauffage.start": ("C4_DIO96_DO", [(3, True), (3, False), (2, True), (2, False)]),
            "chauffage.stop": ("C4_DIO96_DO", [(4, False), (4, True)]),
            "prema.start": ("C4_DIO96_DO", [(5, True), (5, False), (2, True), (2, False)]),
            "prema.stop": ("C4_DIO96_DO", [(6, False), (6, True)]),
            "relays_ht.start": ("C4_DIO96_DO", [(16, True), (16, False), (2, True), (2, False)]),
            "relays_ht.stop": ("C4_DIO96_DO", [(17, False), (17, True)]),
            "modulator.reset": ("C4_DIO96_DO", [(2, True), (2, False)]),
        }
        for operation, (name, fields) in cases.items():
            with self.subTest(operation=operation):
                backend, owner = self.backend(stage_controls_verified=True)
                # Preserve a deliberately non-startup unrelated command field.
                bank = list(backend.commanded_digital[name])
                bank[-1] = not bank[-1]
                backend.commanded_digital[name] = tuple(bank)
                expected = list(bank)
                original = copy.deepcopy(backend.initial_images)
                result = backend.execute_stage(operation, FastCancel(), operator_confirmed=True)
                calls = owner.write_digital_bank.call_args_list
                self.assertEqual(len(calls), len(fields))
                expectations = copy.deepcopy(backend.initial_images["digital"])
                expectations[name] = tuple(bank)
                for number, (call, (index, value)) in enumerate(zip(calls, fields)):
                    target = "C4_DIO96_DO" if operation == "cooling.start" and number >= 4 else name
                    expected = list(expectations[target])
                    expected[index] = value
                    self.assertEqual(call[0], (target, expected))
                    expectations[target] = tuple(expected)
                self.assertEqual(backend.commanded_digital, expectations)
                self.assertEqual(backend.initial_images, original)
                self.assertEqual(result["status"], "COMPLETED")
                self.assertFalse(result["hardware_acknowledged"])
                self.assertIs(backend.owner, owner)

    def test_full_software_banks_are_literal_memory_and_latest_publications_not_ack(self):
        backend, owner = self.backend(stage_controls_verified=True)
        initial = backend.read_snapshot(FastCancel())["stage_state"]
        self.assertEqual(initial["local_banks"]["EPS"], (False,) * 77)
        self.assertEqual(initial["local_banks"]["DPS"], (False,) * 29)
        self.assertIsNone(initial["update_indicator"])
        # A General literal assignment and a stage must share the same EPS RAM.
        backend._stage_assign_status(((8, True),), ((2, False),))
        backend.execute_stage("chauffage.start", FastCancel(), operator_confirmed=True)
        snapshot = backend.read_snapshot(FastCancel())
        state = snapshot["stage_state"]
        self.assertEqual(len(state["local_banks"]["C3_OUT_DIO96"]), 40)
        self.assertEqual(len(state["local_banks"]["C4_OUT_DIO96"]), 32)
        self.assertTrue(state["local_banks"]["EPS"][8])
        self.assertTrue(state["local_banks"]["EPS"][14])
        self.assertFalse(state["local_banks"]["EPS"][12])
        self.assertTrue(state["update_indicator"])
        self.assertTrue(snapshot["software_status_assignments"]["EPS"][14])
        self.assertFalse(state["hardware_acknowledged"])
        self.assertFalse(state["psp_delivery_acknowledged"])
        self.assertEqual(state["publication_storage"], "bounded_latest_per_name_in_RAM")
        for publication in state["publications"].values():
            self.assertFalse(publication["psp_delivered"])
            self.assertFalse(publication["hardware_acknowledged"])
            self.assertEqual(publication["transport"], "LOCAL_RAM_REPLACEMENT_NOT_PSP")
        before = state["publication_count"]
        backend.execute_stage("chauffage.start", FastCancel(), operator_confirmed=True)
        latest = backend.read_snapshot(FastCancel())["stage_state"]
        self.assertGreater(latest["publication_count"], before)
        self.assertLessEqual(len(latest["publications"]), 3)
        # Consumer mutation cannot rewrite the owner's retained publication.
        snapshot["stage_state"]["publications"].clear()
        self.assertTrue(backend.stage_publications)

    def test_false_newval_does_not_write_publish_or_assign(self):
        backend, owner = self.backend(stage_controls_verified=True)
        before = backend._stage_snapshot()
        cancel = FastCancel()
        report = backend.execute_stage("prema.start", cancel, operator_confirmed=True, new_value=False)
        self.assertEqual(report["status"], "NOOP")
        self.assertEqual(backend._stage_snapshot(), before)
        self.assertEqual(cancel.waits, [])
        owner.write_digital_bank.assert_not_called()

    def test_focal_helpers_default_blocked_before_any_effect(self):
        backend, owner = self.backend(stage_controls_verified=True)
        for operation in ("focales.start", "focales.stop"):
            with self.assertRaisesRegex(RuntimeError, "Focal controls not commissioned"):
                backend.execute_stage(operation, FastCancel(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(backend.software_status_assignments, {"EPS": {}, "DPS": {}})

    def test_write_failure_restores_command_image_and_retains_owner(self):
        backend, owner = self.backend(stage_controls_verified=True)
        original = tuple(backend.commanded_digital["C4_DIO96_DO"])
        owner.write_digital_bank.side_effect = [RuntimeError("synthetic write failure"), None]
        with self.assertRaises(StageExecutionError) as caught:
            backend.execute_stage("chauffage.start", FastCancel(), operator_confirmed=True)
        self.assertEqual(backend.commanded_digital["C4_DIO96_DO"], original)
        self.assertEqual(owner.write_digital_bank.call_count, 2)
        self.assertEqual(caught.exception.report["status"], "PARTIAL_FAILURE")
        self.assertEqual(backend.procedure["state"], "INTERRUPTED_OR_FAILED")
        self.assertFalse(caught.exception.report["hardware_acknowledged"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_stop_failure_keeps_later_literal_status_but_never_claims_ack(self):
        backend, owner = self.backend(stage_controls_verified=True)
        owner.write_digital_bank.side_effect = [RuntimeError("synthetic write failure"), None, None]
        with self.assertRaises(StageExecutionError):
            backend.execute_stage("prema.stop", FastCancel(), operator_confirmed=True)
        # Source stop-frame assignments remain literal intent despite failed DO.
        self.assertTrue(backend._stage_read_local(44)[23])
        self.assertFalse(backend.procedure["hardware_acknowledged"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_demo_uses_same_executor_and_explicitly_marks_simulation(self):
        backend = DemoBackend(stage_controls_verified=True)
        backend.initialize(FastCancel())
        result = backend.execute_stage("prema.start", FastCancel(), operator_confirmed=True)
        snapshot = backend.read_snapshot(FastCancel())
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(snapshot["simulated"])
        self.assertFalse(snapshot["hardware_writes"])
        self.assertTrue(snapshot["stage_state"]["local_banks"]["EPS"][20])
        self.assertEqual(backend.resource_count, 0)

    def test_cooling_guard_defaults_disabled_without_owner_or_raw_input(self):
        factory = Mock()
        backend = CardBackend(factory)
        report = backend.execute_cooling_guard(None, FastCancel())
        self.assertEqual(report["status"], "DISABLED")
        self.assertFalse(report["effects_enabled"])
        factory.assert_not_called()

    def test_cooling_guard_requires_both_independent_gates(self):
        for stage_gate, trip_gate in ((False, False), (True, False), (False, True)):
            backend, owner = self.backend(stage_controls_verified=stage_gate,
                                          cooling_trip_verified=trip_gate)
            result = backend.execute_cooling_guard(None, FastCancel())
            self.assertEqual(result["status"], "DISABLED")
            owner.write_digital_bank.assert_not_called()

    def test_cooling_guard_true_uses_supplied_raw_snapshot_without_reading_cards_again(self):
        backend, owner = self.backend(stage_controls_verified=True, cooling_trip_verified=True)
        owner.tasks["C4_DIO96_DI"].read.return_value[19] = True
        snapshot = backend.read_snapshot(FastCancel())
        # Preserve these existing stages: this source branch does not stop them.
        backend._stage_assign_status(((14, True), (20, True), (32, True)), ())
        before_c4 = backend.commanded_digital["C4_DIO96_DO"]
        read_count = owner.tasks["C4_DIO96_DI"].read.call_count
        cancel = FastCancel()
        result = backend.execute_cooling_guard(snapshot, cancel)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["raw_predicate"])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertEqual(cancel.waits, [.15, .4, .15, .1])
        self.assertEqual(owner.tasks["C4_DIO96_DI"].read.call_count, read_count)
        self.assertEqual(owner.write_digital_bank.call_count, 4)
        before_c3 = list(backend.initial_images["digital"]["C3_DIO96_DO"])
        for call, (index, value) in zip(owner.write_digital_bank.call_args_list,
                                        ((1, False), (1, True), (4, False), (4, True))):
            before_c3[index] = value
            self.assertEqual(call[0], ("C3_DIO96_DO", before_c3))
        self.assertEqual(backend.commanded_digital["C4_DIO96_DO"], before_c4)
        self.assertEqual(tuple(backend._stage_read_local(44)[i] for i in (14, 20, 32)),
                         (True, True, True))
        self.assertTrue(backend._stage_read_local(44)[1])
        self.assertTrue(backend._stage_read_local(44)[5])
        self.assertFalse(backend._stage_read_local(36)[1])
        publication = backend.stage_publications["DPS"]
        self.assertEqual(publication["values"], backend._stage_read_local(36))
        self.assertFalse(publication["psp_delivered"])

    def test_cooling_guard_false_arm_has_no_output_status_or_publication_effects(self):
        backend, owner = self.backend(stage_controls_verified=True, cooling_trip_verified=True)
        snapshot = backend.read_snapshot(FastCancel())
        result = backend.execute_cooling_guard(snapshot, FastCancel())
        self.assertEqual(result["status"], "false_arm")
        self.assertFalse(result["callback_execution"])
        self.assertEqual(backend.software_status_assignments, {"EPS": {}, "DPS": {}})
        self.assertEqual(backend.stage_publication_count, 0)
        owner.write_digital_bank.assert_not_called()

    def test_cooling_guard_rejects_mixed_simulation_and_partial_or_coerced_raw_banks(self):
        backend, owner = self.backend(stage_controls_verified=True, cooling_trip_verified=True)
        snapshot = backend.read_snapshot(FastCancel())
        for bad in (dict(snapshot, simulated=True), dict(snapshot, banks={})):
            with self.assertRaises(ValueError):
                backend.execute_cooling_guard(bad, FastCancel())
        for values in ([False], [0] * 64):
            snapshot["banks"]["C4_DIO96_DI"]["values"] = values
            with self.assertRaises(TypeError):
                backend.execute_cooling_guard(snapshot, FastCancel())
        owner.write_digital_bank.assert_not_called()

    def test_cooling_guard_write_failure_retains_diagnostics_and_owner(self):
        from legacy.xp_acq_agent.elyse_agent.acquisition_cooling_trip import CoolingTripError
        backend, owner = self.backend(stage_controls_verified=True, cooling_trip_verified=True)
        owner.tasks["C4_DIO96_DI"].read.return_value[19] = True
        snapshot = backend.read_snapshot(FastCancel())
        owner.write_digital_bank.side_effect = [RuntimeError("synthetic write failure"), None]
        with self.assertRaises(CoolingTripError):
            backend.execute_cooling_guard(snapshot, FastCancel())
        self.assertEqual(backend.last_cooling_guard["status"], "failed")
        self.assertEqual(len(backend.last_cooling_guard["restoration_attempts"]), 1)
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def leave_unrestored_chauffage_pulse(self):
        backend, owner = self.backend(stage_controls_verified=True, focal_off=lambda: None,
                                      stop_wait=lambda _seconds: None)
        # One successful assertion, followed by failures restoring it.
        count = [0]
        def write(_name, _values):
            count[0] += 1
            if count[0] > 1:
                raise RuntimeError("synthetic restore failure")
        owner.write_digital_bank.side_effect = write
        with self.assertRaises(StageExecutionError):
            backend.execute_stage("chauffage.start", FailedWait(), operator_confirmed=True)
        self.assertTrue(backend.commanded_digital["C4_DIO96_DO"][3])
        self.assertEqual(backend._stage_pending_snapshot(), [(15, 3, False)])
        return backend, owner

    def test_general_stop_retries_known_unrestored_fields_before_any_source_bank_write(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        unrelated = list(backend.commanded_digital["C4_DIO96_DO"])
        unrelated[31] = True
        backend.commanded_digital["C4_DIO96_DO"] = tuple(unrelated)
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.general_stop(operator_confirmed=True)
        calls = owner.write_digital_bank.call_args_list
        self.assertEqual(len(calls), 11)  # Recovery, then ten source stop writes.
        for call in calls:
            self.assertEqual(call[0][0], "C4_DIO96_DO")
            self.assertFalse(call[0][1][3])
            self.assertTrue(call[0][1][31])
        self.assertEqual(backend._stage_pending_snapshot(), [])
        self.assertTrue(backend.procedure["command_sequence_completed"])
        self.assertTrue(backend._stage_restoration_origin["restoration_failures"])
        self.assertTrue(backend._stage_restoration_attempts[-1]["succeeded"])
        self.assertIs(backend.owner, owner)

    def test_failed_pending_restore_aborts_general_before_focal_or_source_writes(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        focal_off = Mock()
        backend.focal_off = focal_off
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = RuntimeError("synthetic retry still blocked")
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 1)
        focal_off.assert_not_called()
        self.assertFalse(backend.procedure["command_sequence_completed"])
        self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
        self.assertEqual(backend._stage_pending_snapshot(), [(15, 3, False)])
        self.assertFalse(backend._stage_restoration_attempts[-1]["succeeded"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_other_stage_stop_drains_old_start_before_its_unrelated_full_bank_pulse(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.execute_stage("prema.stop", FastCancel(), operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 3)
        for call in owner.write_digital_bank.call_args_list:
            self.assertFalse(call[0][1][3])
        self.assertEqual(backend._stage_pending_snapshot(), [])

    def test_general_start_drains_old_stage_pulse_before_any_new_general_command(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.general_start(FastCancel(), operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 7)
        for call in owner.write_digital_bank.call_args_list:
            self.assertFalse(call[0][1][3])
        self.assertEqual(backend._stage_pending_snapshot(), [])

    def test_true_cooling_guard_drains_old_c4_pulse_before_c3_trip_effects(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        backend.cooling_trip_verified = True
        owner.tasks["C4_DIO96_DI"].read.return_value[19] = True
        snapshot = backend.read_snapshot(FastCancel())
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.execute_cooling_guard(snapshot, FastCancel())
        calls = owner.write_digital_bank.call_args_list
        self.assertEqual(len(calls), 5)
        self.assertEqual(calls[0][0][0], "C4_DIO96_DO")
        self.assertFalse(calls[0][0][1][3])
        self.assertTrue(all(call[0][0] == "C3_DIO96_DO" for call in calls[1:]))
        self.assertEqual(backend._stage_pending_snapshot(), [])

    def test_empty_or_unqualified_events_never_drain_an_old_pending_pulse(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.execute_stage("prema.stop", FastCancel(), operator_confirmed=True, new_value=False)
        with self.assertRaisesRegex(RuntimeError, "Focal controls not commissioned"):
            backend.execute_stage("focales.start", FastCancel(), operator_confirmed=True)
        backend.cooling_trip_verified = True
        backend.execute_cooling_guard(backend.read_snapshot(FastCancel()), FastCancel())
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(backend._stage_pending_snapshot(), [(15, 3, False)])

    def test_cooling_pending_c3_field_is_recovered_before_general_c4_writes(self):
        from legacy.xp_acq_agent.elyse_agent.acquisition_cooling_trip import CoolingTripError
        backend, owner = self.backend(stage_controls_verified=True, cooling_trip_verified=True,
                                      focal_off=lambda: None, stop_wait=lambda _seconds: None)
        owner.tasks["C4_DIO96_DI"].read.return_value[19] = True
        snapshot = backend.read_snapshot(FastCancel())
        count = [0]
        def write(_name, _values):
            count[0] += 1
            if count[0] > 1:
                raise RuntimeError("synthetic C3 restore failure")
        owner.write_digital_bank.side_effect = write
        with self.assertRaises(CoolingTripError):
            backend.execute_cooling_guard(snapshot, FailedWait())
        self.assertEqual(backend._stage_pending_snapshot(), [(17, 1, True)])
        self.assertFalse(backend.commanded_digital["C3_DIO96_DO"][1])
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.general_stop(operator_confirmed=True)
        first = owner.write_digital_bank.call_args_list[0][0]
        self.assertEqual(first[0], "C3_DIO96_DO")
        self.assertTrue(first[1][1])
        self.assertEqual(backend._stage_pending_snapshot(), [])

    def test_ht_gate_defaults_false_and_is_independent_from_feedback_qualification(self):
        factory = Mock()
        backend = CardBackend(factory, stage_controls_verified=True, ht_feedback_verified=True)
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset"):
            with self.assertRaisesRegex(RuntimeError, "HT controls not commissioned"):
                backend.execute_stage(operation, FastCancel(), operator_confirmed=True)
        factory.assert_not_called()
        self.assertFalse(backend.ht_controls_verified)
        backend, owner = self.backend(stage_controls_verified=True)
        self.assertFalse(backend._stage_snapshot()["ht_controls_verified"])
        owner.write_digital_bank.assert_not_called()

    def test_ht_commissioning_flag_is_an_exact_boolean_for_card_and_demo(self):
        for value in (None, 0, 1, "yes"):
            for constructor in (CardBackend, DemoBackend):
                with self.assertRaises(ValueError):
                    constructor(ht_controls_verified=value)

    def test_ht_gate_false_prevents_pending_recovery_and_every_procedure_effect(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        before = backend._stage_snapshot()
        assignments = copy.deepcopy(backend.software_status_assignments)
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        cancel = FastCancel()
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset"):
            with self.assertRaisesRegex(RuntimeError, "HT controls not commissioned"):
                backend.execute_stage(operation, cancel, operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(cancel.waits, [])
        self.assertEqual(backend._stage_snapshot(), before)
        self.assertEqual(backend.software_status_assignments, assignments)

    def test_ht_gate_alone_does_not_replace_stage_confirmation_profile_or_owner_guards(self):
        backend, owner = self.backend(ht_controls_verified=True)
        with self.assertRaisesRegex(RuntimeError, "stage controls not commissioned"):
            backend.execute_stage("alimentation_ht.start", FastCancel(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        backend, owner = self.backend(stage_controls_verified=True, ht_controls_verified=True,
                                      control_profile="general_only_test")
        with self.assertRaisesRegex(RuntimeError, "General-only"):
            backend.execute_stage("alimentation_ht.stop", FastCancel(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        backend = CardBackend(stage_controls_verified=True, ht_controls_verified=True)
        with self.assertRaises(ValueError):
            backend.execute_stage("alimentation_ht.reset", FastCancel())
        with self.assertRaisesRegex(RuntimeError, "initialized"):
            backend.execute_stage("alimentation_ht.reset", FastCancel(), operator_confirmed=True)

    def test_all_three_ht_paths_write_only_the_two_source_c4_images(self):
        cases = (("alimentation_ht.start", 18, True, False, 15, ((45, True), (49, False))),
                 ("alimentation_ht.stop", 19, False, True, 17, ((45, False), (49, True))),
                 ("alimentation_ht.reset", 20, True, False, 16, ()))
        for operation, index, asserted, released, dps, eps in cases:
            with self.subTest(operation=operation):
                backend, owner = self.backend(stage_controls_verified=True, ht_controls_verified=True)
                c4 = list(backend.commanded_digital["C4_DIO96_DO"])
                c4[31] = True
                backend.commanded_digital["C4_DIO96_DO"] = tuple(c4)
                before_analog = copy.deepcopy(backend.commanded_analog)
                before_start = owner.start_legacy_counters.call_count
                self.assertFalse(backend.ht_feedback_verified)  # Independent qualification.
                cancel = FastCancel()
                result = backend.execute_stage(operation, cancel, operator_confirmed=True)
                self.assertEqual(result["status"], "COMPLETED")
                self.assertEqual(cancel.waits, [.15, .1])
                self.assertEqual(owner.write_digital_bank.call_count, 2)
                for call, value in zip(owner.write_digital_bank.call_args_list, (asserted, released)):
                    c4[index] = value
                    self.assertEqual(call[0], ("C4_DIO96_DO", c4))
                self.assertEqual(backend.software_status_assignments["DPS"], {dps: False})
                self.assertEqual(backend.software_status_assignments["EPS"], dict(eps))
                self.assertEqual(backend.commanded_analog, before_analog)
                self.assertEqual(owner.start_legacy_counters.call_count, before_start)
                owner.write_analog_logical_bank.assert_not_called()
                for task in owner.tasks.values():
                    task.start.assert_not_called()
                    task.stop.assert_not_called()
                    task.read.assert_not_called()
                self.assertEqual(set(backend.stage_publications), {"DPS", "EPS", "C4_OUT_DIO96"})
                self.assertFalse(result["hardware_acknowledged"])

    def test_ht_false_newval_never_recovers_pending_commands_or_updates_status(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        backend.ht_controls_verified = True
        before = backend._stage_snapshot()
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        cancel = FastCancel()
        for operation in ("alimentation_ht.start", "alimentation_ht.stop", "alimentation_ht.reset"):
            result = backend.execute_stage(operation, cancel, operator_confirmed=True, new_value=False)
            self.assertEqual(result["status"], "NOOP")
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(cancel.waits, [])
        self.assertEqual(backend._stage_snapshot(), before)

    def test_ht_publications_follow_chain_but_keep_independent_frame_entry_snapshots(self):
        backend, owner = self.backend(stage_controls_verified=True, ht_controls_verified=True)
        original_publish = backend._stage_publish
        attempted = []
        def publish(name, bank, values):
            attempted.append(name)
            original_publish(name, bank, values)
            if name == "DPS":
                # Simulate an independent local writer after frame-entry reads.
                eps = list(backend._stage_status[44])
                eps[60] = True
                backend._stage_status[44] = tuple(eps)
                c4 = list(backend.commanded_digital["C4_DIO96_DO"])
                c4[31] = True
                backend.commanded_digital["C4_DIO96_DO"] = tuple(c4)
        backend._stage_publish = publish
        backend.execute_stage("alimentation_ht.start", FastCancel(), operator_confirmed=True)
        self.assertEqual(attempted, ["DPS", "EPS", "C4_OUT_DIO96"])
        publications = backend.stage_publications
        self.assertEqual([publications[name]["sequence"] for name in attempted], [1, 2, 3])
        self.assertTrue(backend._stage_read_local(44)[60])
        self.assertFalse(publications["EPS"]["values"][60])
        self.assertTrue(backend._stage_read_local(15)[31])
        self.assertFalse(publications["C4_OUT_DIO96"]["values"][31])
        self.assertTrue(publications["EPS"]["values"][45])
        self.assertFalse(publications["EPS"]["psp_delivered"])

    def test_ht_publication_failure_short_circuits_later_chain_without_ack(self):
        backend, owner = self.backend(stage_controls_verified=True, ht_controls_verified=True)
        original_publish = backend._stage_publish
        attempted = []
        def publish(name, bank, values):
            attempted.append(name)
            if name == "EPS":
                raise RuntimeError("synthetic publication boundary failure")
            original_publish(name, bank, values)
        backend._stage_publish = publish
        with self.assertRaises(StageExecutionError):
            backend.execute_stage("alimentation_ht.start", FastCancel(), operator_confirmed=True)
        self.assertEqual(attempted, ["DPS", "EPS"])
        self.assertEqual(set(backend.stage_publications), {"DPS"})
        self.assertTrue(backend._stage_read_local(44)[45])  # Source literal, not physical ACK.
        self.assertFalse(backend.procedure["hardware_acknowledged"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_ht_assertion_restore_failure_is_drained_before_later_ht_stop(self):
        backend, owner = self.backend(stage_controls_verified=True, ht_controls_verified=True)
        count = [0]
        def write(_name, _values):
            count[0] += 1
            if count[0] > 1:
                raise RuntimeError("synthetic HT restore failure")
        owner.write_digital_bank.side_effect = write
        with self.assertRaises(StageExecutionError):
            backend.execute_stage("alimentation_ht.start", FailedWait(), operator_confirmed=True)
        self.assertEqual(backend._stage_pending_snapshot(), [(15, 18, False)])
        self.assertTrue(backend.commanded_digital["C4_DIO96_DO"][18])
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        backend.execute_stage("alimentation_ht.stop", FastCancel(), operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 3)
        for call in owner.write_digital_bank.call_args_list:
            self.assertFalse(call[0][1][18])
        self.assertEqual(backend._stage_pending_snapshot(), [])
        owner.write_analog_logical_bank.assert_not_called()

    def test_ht_demo_uses_independent_gate_and_same_literal_executor(self):
        backend = DemoBackend(stage_controls_verified=True)
        backend.initialize(FastCancel())
        with self.assertRaisesRegex(RuntimeError, "HT controls not commissioned"):
            backend.execute_stage("alimentation_ht.start", FastCancel(), operator_confirmed=True)
        backend = DemoBackend(stage_controls_verified=True, ht_controls_verified=True)
        backend.initialize(FastCancel())
        result = backend.execute_stage("alimentation_ht.stop", FastCancel(), operator_confirmed=True)
        snapshot = backend.read_snapshot(FastCancel())
        self.assertEqual(result["status"], "COMPLETED")
        self.assertTrue(snapshot["simulated"])
        self.assertFalse(snapshot["hardware_writes"])
        self.assertTrue(snapshot["stage_state"]["ht_controls_verified"])
        self.assertTrue(snapshot["stage_state"]["local_banks"]["EPS"][49])

    def test_focal_flag_exact_boolean_and_default_native_resources_unqualified(self):
        for value in (None, 0, 1, "yes"):
            for constructor in (CardBackend, DemoBackend):
                with self.assertRaises(ValueError):
                    constructor(focal_controls_verified=value)
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True)
        self.assertIs(getattr(backend.focal_command, "resources_verified", None), False)
        cancel = FastCancel()
        with self.assertRaisesRegex(RuntimeError, "serial resources not commissioned"):
            backend.execute_stage("focales.start", cancel, operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(cancel.waits, [])
        self.assertEqual(backend.stage_publication_count, 0)
        self.assertEqual(backend.software_status_assignments, {"EPS": {}, "DPS": {}})

    def test_focal_gate_is_independent_and_checked_before_adapter_or_recovery_effects(self):
        adapter = FakeFocalCommand()
        backend, owner = self.backend(stage_controls_verified=True, focal_command=adapter)
        adapter.calls[:] = []
        before = backend._stage_snapshot()
        for operation in ("focales.start", "focales.stop"):
            with self.assertRaisesRegex(RuntimeError, "Focal controls not commissioned"):
                backend.execute_stage(operation, FastCancel(), operator_confirmed=True)
        self.assertEqual(adapter.calls, [])
        self.assertEqual(backend._stage_snapshot(), before)
        owner.write_digital_bank.assert_not_called()
        backend = CardBackend(focal_controls_verified=True, focal_command=adapter)
        with self.assertRaisesRegex(RuntimeError, "stage controls not commissioned"):
            backend.execute_stage("focales.start", FastCancel(), operator_confirmed=True)

    def test_focal_false_newval_does_not_check_ready_or_restore_pending_pulse(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        adapter = FakeFocalCommand(resources_verified=False)
        adapter.blocked = True
        backend.focal_command = adapter
        backend.focal_controls_verified = True
        before = backend._stage_snapshot()
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        cancel = FastCancel()
        for operation in ("focales.start", "focales.stop"):
            result = backend.execute_stage(operation, cancel, operator_confirmed=True, new_value=False)
            self.assertEqual(result["status"], "NOOP")
        self.assertEqual(adapter.calls, [])
        self.assertEqual(cancel.waits, [])
        self.assertEqual(backend._stage_snapshot(), before)
        owner.write_digital_bank.assert_not_called()

    def test_focal_ready_is_checked_before_c4_pulse_pending_recovery_or_wait(self):
        backend, owner = self.leave_unrestored_chauffage_pulse()
        adapter = FakeFocalCommand()
        adapter.ready_error = RuntimeError("synthetic reviewed DLL hash / x86 readiness failure")
        backend.focal_command = adapter
        backend.focal_controls_verified = True
        owner.write_digital_bank.reset_mock()
        owner.write_digital_bank.side_effect = None
        cancel = FastCancel()
        with self.assertRaisesRegex(RuntimeError, "readiness failure"):
            backend.execute_stage("focales.start", cancel, operator_confirmed=True)
        self.assertEqual(adapter.calls, [("ready",)])
        self.assertEqual(backend._stage_pending_snapshot(), [(15, 3, False)])
        self.assertEqual(cancel.waits, [])
        owner.write_digital_bank.assert_not_called()

    def test_focal_start_exact_nominal_do_status_and_helper_sequence(self):
        adapter = FakeFocalCommand()
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True,
                                      focal_command=adapter)
        log = []
        def write(name, bank):
            log.append(("write", name, tuple(bank)))
        owner.write_digital_bank.side_effect = write
        def helper(output_enabled, cancelled):
            log.append(("helper", output_enabled))
            return dict(simulated=True, hardware_acknowledged=False)
        adapter.execute_callback = helper
        cancel = FastCancel()
        result = backend.execute_stage("focales.start", cancel, operator_confirmed=True)
        self.assertEqual(result["status"], "COMPLETED")
        fields = ((7, True), (7, False), (2, True), (2, False))
        expected = list(backend.initial_images["digital"]["C4_DIO96_DO"])
        rows = [row for row in log if row[0] == "write"]
        for row, (index, value) in zip(rows, fields):
            expected[index] = value
            self.assertEqual(row, ("write", "C4_DIO96_DO", tuple(expected)))
        self.assertEqual(len(rows), 4)
        self.assertEqual(log[2], ("helper", True))
        self.assertEqual(cancel.waits, [.15, 29.0, 1.5, .15, .25, .1])
        self.assertEqual(backend.software_status_assignments,
                         {"DPS": {10: False}, "EPS": {30: False, 32: True, 35: False}})
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", True)])
        self.assertFalse(backend._stage_snapshot()["hardware_acknowledged"])
        owner.write_analog_logical_bank.assert_not_called()

    def test_focal_stop_exact_nominal_off_then_two_do_images_and_status(self):
        adapter = FakeFocalCommand()
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True,
                                      focal_command=adapter)
        log = []
        owner.write_digital_bank.side_effect = lambda name, values: log.append(("write", values[8]))
        adapter.execute_callback = lambda enabled, cancelled: log.append(("helper", enabled))
        cancel = FastCancel()
        result = backend.execute_stage("focales.stop", cancel, operator_confirmed=True)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(log, [("helper", False), ("write", False), ("write", True)])
        self.assertEqual(cancel.waits, [.5, .15, .15, .1])
        self.assertEqual(backend.software_status_assignments,
                         {"DPS": {11: False}, "EPS": {32: False, 33: False, 35: True}})
        self.assertEqual(backend.stage_publications["DPS"]["values"], backend._stage_read_local(36))
        self.assertFalse(backend.stage_publications["DPS"]["psp_delivered"])
        owner.write_analog_logical_bank.assert_not_called()

    def make_failed_focal_on(self, cancelled=False, returned_pending=False):
        adapter = FakeFocalCommand()
        focal_off = Mock()
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True,
                                      focal_command=adapter, focal_off=focal_off,
                                      stop_wait=lambda seconds: None)
        cancel = FastCancel()
        def fail(enabled, ignored_cancelled):
            adapter.blocked = True
            cancel.cancelled = cancelled
            if returned_pending:
                return dict(callback_returned=True)
            raise RuntimeError("synthetic native helper / cleanup failure")
        adapter.execute_callback = fail
        with self.assertRaises(StageExecutionError):
            backend.execute_stage("focales.start", cancel, operator_confirmed=True)
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", True)])
        return backend, owner, adapter, focal_off

    def test_failed_or_cancelled_native_on_cannot_race_general_off_or_other_outputs(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                backend, owner, adapter, focal_off = self.make_failed_focal_on(cancelled)
                owner.write_digital_bank.reset_mock()
                with self.assertRaises(RuntimeError):
                    backend.general_start(FastCancel(), operator_confirmed=True)
                with self.assertRaises(RuntimeError):
                    backend.general_stop(operator_confirmed=True)
                with self.assertRaises(RuntimeError):
                    backend.execute_stage("prema.stop", FastCancel(), operator_confirmed=True)
                focal_off.assert_not_called()
                owner.write_digital_bank.assert_not_called()
                self.assertFalse(backend.procedure.get("command_sequence_completed", False))
                self.assertIs(backend.owner, owner)
                self.assertTrue(backend._stage_snapshot()["focal_helper_results"])
                self.assertEqual(backend._stage_snapshot()["focal_command_diagnostics"]["pending_worker_count"], 1)
                json.dumps(backend._stage_snapshot(), allow_nan=False)

    def test_returned_helper_with_unconfirmed_cleanup_is_failure_not_eps_ok(self):
        backend, owner, adapter, focal_off = self.make_failed_focal_on(returned_pending=True)
        self.assertEqual(backend._stage_read_local(44)[32], False)
        self.assertEqual(backend._focal_helper_results["1_Focales ON.vi"]["state"], "FAILED_OR_CANCELLED")
        self.assertIs(backend.owner, owner)

    def test_unconfirmed_on_worker_blocks_close_and_reinitialization_until_quiescent(self):
        backend, owner, adapter, focal_off = self.make_failed_focal_on()
        with self.assertRaises(RuntimeError):
            backend.close()
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()
        with self.assertRaises(RuntimeError):
            backend.initialize(FastCancel(), startup_confirmed=True)
        adapter.blocked = False  # Simulated confirmed process death/reap.
        backend.general_stop(operator_confirmed=True)
        focal_off.assert_called_once_with()
        self.assertTrue(backend.procedure["command_sequence_completed"])
        backend.close()
        owner.close.assert_called_once_with()
        self.assertIsNone(backend.owner)
        self.assertEqual(backend.commanded_digital, {})

    def test_cold_initialize_denies_pending_native_worker_before_factory(self):
        adapter = FakeFocalCommand()
        adapter.blocked = True
        factory = Mock()
        backend = CardBackend(factory, focal_command=adapter)
        with self.assertRaises(RuntimeError):
            backend.initialize(FastCancel(), startup_confirmed=True)
        factory.assert_not_called()
        self.assertIsNone(backend.owner)

    def test_focal_helper_results_never_export_raw_native_objects(self):
        adapter = FakeFocalCommand()
        adapter.execute_callback = lambda enabled, cancelled: object()
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True,
                                      focal_command=adapter)
        backend.execute_stage("focales.start", FastCancel(), operator_confirmed=True)
        json.dumps(backend.read_snapshot(FastCancel()), allow_nan=False)
        returned = backend._stage_snapshot()["focal_helper_results"]["1_Focales ON.vi"]["returned"]
        self.assertEqual(returned["returned_type"], "object")
        self.assertFalse(returned["retained"])

    def test_demo_focal_is_pure_ram_and_rejects_unlabelled_native_injection(self):
        with self.assertRaises(ValueError):
            DemoBackend(focal_command=object())
        backend = DemoBackend(stage_controls_verified=True, focal_controls_verified=True)
        backend.initialize(FastCancel())
        backend.execute_stage("focales.start", FastCancel(), operator_confirmed=True)
        snapshot = backend.read_snapshot(FastCancel())
        self.assertTrue(snapshot["simulated"])
        self.assertFalse(snapshot["hardware_writes"])
        self.assertTrue(snapshot["stage_state"]["focal_controls_verified"])
        self.assertTrue(snapshot["stage_state"]["local_banks"]["EPS"][32])
        self.assertFalse(snapshot["stage_state"]["focal_helper_results"]["1_Focales ON.vi"]["returned"]
                         ["native_calls"])
        json.dumps(snapshot, allow_nan=False)

    def test_default_general_off_uses_same_owned_adapter_without_enabling_focal_on(self):
        adapter = FakeFocalCommand()
        backend, owner = self.backend(focal_command=adapter, stop_wait=lambda seconds: None)
        self.assertFalse(backend.focal_controls_verified)
        self.assertIs(backend.focal_command, adapter)
        backend.general_stop(operator_confirmed=True)
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", False)])
        self.assertEqual(owner.write_digital_bank.call_count, 10)
        self.assertNotIn("1_Focales ON.vi", backend._focal_helper_results)
        self.assertEqual(backend._focal_helper_results["1_Focales OFF.vi"]["state"],
                         "CALLBACK_COMPLETED_NOT_HARDWARE_ACK")

    def test_failed_general_off_retains_same_worker_owner_and_blocks_later_on_and_close(self):
        adapter = FakeFocalCommand()
        backend, owner = self.backend(stage_controls_verified=True, focal_controls_verified=True,
                                      focal_command=adapter, stop_wait=lambda seconds: None)
        def fail_off(enabled, cancelled):
            self.assertIs(enabled, False)
            adapter.blocked = True
            raise RuntimeError("synthetic OFF worker unconfirmed after timeout")
        adapter.execute_callback = fail_off
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", False)])
        self.assertFalse(backend.procedure["command_sequence_completed"])
        owner.write_digital_bank.assert_not_called()
        with self.assertRaises(RuntimeError):
            backend.execute_stage("focales.start", FastCancel(), operator_confirmed=True)
        with self.assertRaises(RuntimeError):
            backend.close()
        owner.close.assert_not_called()
        self.assertIs(backend.owner, owner)
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", False)])
        adapter.blocked = False
        adapter.execute_callback = None
        backend.general_stop(operator_confirmed=True)
        self.assertTrue(backend.procedure["command_sequence_completed"])
        backend.close()
        owner.close.assert_called_once_with()

    def test_known_legacy_off_adapter_is_normalized_to_owned_command_without_native_calls(self):
        legacy = ChromaFocalStop(dll_path=r"C:\offline\chr62000.dll", resources_verified=False, timeout=4)
        backend = CardBackend(focal_off=legacy)
        self.assertIsNot(backend.focal_off, legacy)
        self.assertEqual(backend.focal_command.dll_path, legacy.dll_path)
        self.assertIs(backend.focal_command.resources_verified, False)
        self.assertEqual(backend.focal_command.timeout, 4)
        self.assertEqual(backend.focal_command.pending_worker_count, 0)
        self.assertIsNone(backend.owner)

    def test_matching_legacy_off_and_owned_command_normalize_but_conflicts_reject_cold(self):
        legacy = ChromaFocalStop(dll_path=r"C:\offline\chr62000.dll", resources_verified=True, timeout=4)
        legacy.ensure_ready = Mock(side_effect=AssertionError("Legacy native OFF must not be called"))
        adapter = FakeFocalCommand()
        adapter.dll_path, adapter.timeout = legacy.dll_path, legacy.timeout
        backend, owner = self.backend(focal_off=legacy, focal_command=adapter, stop_wait=lambda seconds: None)
        backend.general_stop(operator_confirmed=True)
        legacy.ensure_ready.assert_not_called()
        self.assertEqual([call for call in adapter.calls if call[0] == "execute"], [("execute", False)])
        factory = Mock()
        adapter.timeout = 5
        with self.assertRaisesRegex(ValueError, "Conflicting legacy OFF"):
            CardBackend(factory, focal_off=legacy, focal_command=adapter)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
