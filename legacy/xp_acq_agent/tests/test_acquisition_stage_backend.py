"""Offline real CardBackend methods with an injected fake NI owner only."""
import copy
import threading
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution import StageExecutionError
from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import GeneralStopError
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

    def test_unsupplied_focal_and_ht_helpers_never_partly_execute(self):
        backend, owner = self.backend(stage_controls_verified=True)
        for operation in ("focales.start", "focales.stop", "alimentation_ht.start", "alimentation_ht.stop"):
            with self.assertRaises(ValueError):
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
        with self.assertRaises(ValueError):
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


if __name__ == "__main__":
    unittest.main()
