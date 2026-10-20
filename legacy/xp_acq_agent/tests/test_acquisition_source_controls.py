"""Integrated source controls on fake owners only; Python 3.4 compatible."""
import copy
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.tests.test_acquisition_runtime import FakeBackend, wait_state
from legacy.xp_acq_agent.tests.test_acquisition_stage_backend import fake_owner


class Cancel(object):
    def __init__(self):
        self.waits = []
        self.cancelled = False

    def is_set(self):
        return self.cancelled

    def wait(self, seconds):
        self.waits.append(seconds)
        return self.cancelled


def backend_fixture(**overrides):
    owner, waits = fake_owner(), []
    owner.counter_channels = {number: SimpleNamespace(co_pulse_done=True) for number in (3, 4)}
    for number in (3, 4):
        task = Mock()
        task.is_task_done.side_effect = AssertionError("TaskDone is not source PulseDone")
        owner.tasks["C10_NI6602_CO_{0}".format(number)] = task
    owner.start_counter.side_effect = lambda number: owner.tasks["C10_NI6602_CO_{0}".format(number)].start()
    owner.stop_counter.side_effect = lambda number: owner.tasks["C10_NI6602_CO_{0}".format(number)].stop()
    owner.read_counter_pulse_done.side_effect = lambda number: owner.counter_channels[number].co_pulse_done
    owner.close.side_effect = owner.tasks.clear
    flags = dict(stage_controls_verified=True, counter_controls_verified=True,
                 ht_voltage_controls_verified=True, outer_stop_verified=True)
    flags.update(overrides)
    backend = CardBackend(Mock(return_value=owner), stop_wait=waits.append, **flags)
    backend.initialize(Cancel(), startup_confirmed=True)
    return backend, owner, waits


class SourceBackendTests(unittest.TestCase):
    def test_independent_exact_false_gates_refuse_before_driver_or_state_change(self):
        for flag, action in (
                ("counter_controls_verified", lambda b: b.execute_impulsion("modulator_impulse.start", Cancel(), True)),
                ("ht_voltage_controls_verified", lambda b: b.set_ht_voltage(12.7, Cancel(), True)),
                ("outer_stop_verified", lambda b: b.outer_controlled_stop(True))):
            backend, owner, _ = backend_fixture(**{flag: False})
            with self.assertRaises(RuntimeError):
                action(backend)
            owner.start_counter.assert_not_called()
            owner.stop_counter.assert_not_called()
            owner.write_analog_logical_bank.assert_not_called()
            owner.write_digital_bank.assert_not_called()
            owner.close.assert_not_called()
            self.assertIs(backend.owner, owner)
        for flag in ("counter_controls_verified", "ht_voltage_controls_verified", "outer_stop_verified"):
            with self.assertRaises(ValueError):
                CardBackend(**{flag: 1})
            with self.assertRaises(ValueError):
                DemoBackend(**{flag: True})

    def test_ht_whole_bank_preserved_and_failed_write_not_remembered_as_success(self):
        backend, owner, _ = backend_fixture()
        before = copy.deepcopy(backend.commanded_analog)
        result = backend.set_ht_voltage(12.7, Cancel(), True)
        name, vector = owner.write_analog_logical_bank.call_args[0]
        self.assertEqual(name, "C9NI6703")
        self.assertEqual(vector[0], 12.7)
        self.assertEqual(vector[1:], before[name][1:])
        self.assertFalse(result["hardware_acknowledged"])
        owner.write_analog_logical_bank.side_effect = RuntimeError("synthetic applied-or-not AO fault")
        with self.assertRaises(Exception):
            backend.set_ht_voltage(12.6, Cancel(), True)
        self.assertEqual(backend.commanded_analog[name][0], 12.7)
        self.assertTrue(backend.ht_command_uncertain)
        self.assertTrue(backend.last_ht_command["command_uncertain"])
        owner.close.assert_not_called()

    def test_invalid_ht_and_unreleased_general_never_reach_any_control_callback(self):
        backend, owner, _ = backend_fixture()
        for value in (True, float("nan"), float("inf"), 20.01, 10 ** 1000, "12.7"):
            with self.assertRaises(ValueError):
                backend.set_ht_voltage(value, Cancel(), True)
        for field in (0, 2):
            image = list(backend.commanded_digital["C4_DIO96_DO"])
            image[0] = image[2] = False
            image[field] = True
            backend.commanded_digital["C4_DIO96_DO"] = tuple(image)
            with self.assertRaises(RuntimeError):
                backend.set_ht_voltage(6.0, Cancel(), True)
            with self.assertRaises(RuntimeError):
                backend.execute_impulsion("modulator_impulse.start", Cancel(), True)
        owner.start_counter.assert_not_called()
        owner.write_analog_logical_bank.assert_not_called()
        owner.write_digital_bank.assert_not_called()

    def test_impulsion_source_start_stop_reuses_tasks_and_keeps_eps42_asymmetry(self):
        backend, owner, _ = backend_fixture()
        cancel = Cancel()
        backend.execute_impulsion("modulator_impulse.start", cancel, True)
        self.assertEqual(owner.start_counter.call_args_list, [((3,),), ((4,),)])
        self.assertTrue(backend._stage_read_local(44)[52])
        self.assertFalse(backend._stage_read_local(44)[55])
        backend.execute_impulsion("modulator_impulse.stop", cancel, True)
        self.assertEqual(owner.stop_counter.call_args_list, [((3,),), ((4,),)])
        self.assertFalse(backend._stage_read_local(44)[52])
        self.assertTrue(backend._stage_read_local(44)[42])
        self.assertEqual(set(backend.stage_publications), {"DPS", "EPS"})
        self.assertNotIn(3, backend.started_counters)
        self.assertNotIn(4, backend.started_counters)
        for number in (3, 4):
            owner.tasks["C10_NI6602_CO_{0}".format(number)].is_task_done.assert_not_called()
        backend.factory.assert_called_once()
        owner.close.assert_not_called()

    def test_failed_counter_stop_retained_and_blocks_next_energy_command(self):
        backend, owner, _ = backend_fixture()
        owner.stop_counter.side_effect = lambda number: (_ for _ in ()).throw(RuntimeError("counter stop fault"))
        with self.assertRaises(Exception):
            backend.execute_impulsion("modulator_impulse.stop", Cancel(), True)
        self.assertEqual(backend._pending_counter_stops, {3, 4})
        with self.assertRaises(Exception):
            backend.set_ht_voltage(6.0, Cancel(), True)
        owner.write_analog_logical_bank.assert_not_called()
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_outer_stop_all_phases_preserve_fields_without_releasing_or_claiming_zero(self):
        backend, owner, waits = backend_fixture()
        before = copy.deepcopy(backend.commanded_analog)
        result = backend.outer_controlled_stop(True)
        self.assertEqual(backend.commanded_analog["C9NI6703"][0], 6.5)
        self.assertEqual(backend.commanded_analog["C6NI6703"][8], before["C6NI6703"][8])
        self.assertEqual(backend.commanded_analog["C7NI6703"][2], before["C7NI6703"][2])
        self.assertEqual(backend._source_scalars[46], True)
        self.assertEqual(backend._source_scalars[47], False)
        self.assertEqual(backend._source_scalars[50], 0.0)
        self.assertEqual(owner.stop_counter.call_count, 2)
        self.assertFalse(result["hardware_acknowledged"])
        self.assertAlmostEqual(sum(waits), 12.852)  # Fixed12.85s + two final1ms pulse polls.
        self.assertEqual(backend.stage_publications, {})  # No invented outer PSP writes.
        owner.close.assert_not_called()
        self.assertIs(backend.owner, owner)

    def test_outer_failure_retains_owner_and_never_reaches_cooling_off(self):
        backend, owner, _ = backend_fixture()
        owner.stop_counter.side_effect = RuntimeError("stop unconfirmed")
        with self.assertRaises(Exception):
            backend.outer_controlled_stop(True)
        self.assertEqual(backend._pending_counter_stops, {3, 4})
        self.assertNotIn(46, backend._source_scalars)
        self.assertFalse(any(call[0][0] == "C3_DIO96_DO" for call in owner.write_digital_bank.call_args_list))
        owner.close.assert_not_called()

    def test_outer_bank_writes_release_interrupted_general_and_raz(self):
        backend, owner, _ = backend_fixture()
        values = list(backend.commanded_digital["C4_DIO96_DO"])
        values[0] = values[2] = True
        backend.commanded_digital["C4_DIO96_DO"] = tuple(values)
        backend.outer_controlled_stop(True)
        for call in owner.write_digital_bank.call_args_list:
            if call[0][0] == "C4_DIO96_DO":
                self.assertIs(call[0][1][0], False)
                self.assertIs(call[0][1][2], False)
        self.assertEqual(backend._pending_stage_restorations, {})

    def test_applied_then_failed_ht_write_blocks_stale_ramp_and_new_energy(self):
        backend, owner, _ = backend_fixture()
        physical = {}

        def apply_then_fail(name, vector):
            physical[name] = tuple(vector)
            raise RuntimeError("applied but acknowledgement lost")

        owner.write_analog_logical_bank.side_effect = apply_then_fail
        with self.assertRaises(Exception):
            backend.set_ht_voltage(12.7, Cancel(), True)
        self.assertEqual(physical["C9NI6703"][0], 12.7)
        self.assertEqual(backend.commanded_analog["C9NI6703"][0], 6.5)
        for action in (lambda: backend.set_ht_voltage(6.0, Cancel(), True),
                       lambda: backend.execute_impulsion("modulator_impulse.start", Cancel(), True),
                       lambda: backend.execute_stage("chauffage.start", Cancel(), True),
                       lambda: backend.general_start(Cancel(), True),
                       lambda: backend._lower_ht_shutdown_command(6.4)):
            with self.assertRaises(RuntimeError):
                action()
        with self.assertRaises(Exception):
            backend.outer_controlled_stop(True)
        self.assertEqual(owner.write_analog_logical_bank.call_count, 1)
        self.assertEqual(owner.stop_counter.call_count, 2)  # Safe-stop cleanup still attempted.
        self.assertNotIn(46, backend._source_scalars)  # Never claims completed outer stop.
        self.assertTrue(backend.ht_command_uncertain)
        self.assertIs(backend.owner, owner)
        owner.start_counter.assert_not_called()
        owner.close.assert_not_called()


class RuntimeBackend(FakeBackend):
    def __init__(self):
        FakeBackend.__init__(self)
        self.stage_controls_verified = self.counter_controls_verified = True
        self.ht_voltage_controls_verified = self.outer_stop_verified = True
        self.calls = []
        self.fail_control = False
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()

    def record(self, name):
        self.calls.append((name, threading.current_thread().ident))
        self.entered.set()
        self.release.wait(2)
        if self.fail_control:
            raise RuntimeError("synthetic control fault")

    def execute_impulsion(self, operation, cancel, operator_confirmed=False):
        self.record(operation)

    def set_ht_voltage(self, command_kv, cancel, operator_confirmed=False):
        self.record(("HT", command_kv))

    def outer_controlled_stop(self, operator_confirmed=False):
        self.record("outer.stop")

    def general_stop(self, operator_confirmed=False):
        self.record("general.stop")


class SourceRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.backend = RuntimeBackend()
        self.runtime = AcquisitionRuntime(lambda: self.backend, period=.02)
        self.runtime.start()
        self.runtime.initialize(True)
        wait_state(self.runtime, "RUNNING")

    def tearDown(self):
        self.backend.release.set()
        self.backend.fail_control = False
        if self.runtime.snapshot()["state"] == "EXECUTING":
            wait_state(self.runtime, "RUNNING")
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(2))

    def test_separate_runtime_gates_and_exact_types_do_not_queue_or_invoke(self):
        self.backend.counter_controls_verified = False
        self.backend.ht_voltage_controls_verified = False
        self.backend.outer_stop_verified = False
        for action in (lambda: self.runtime.stage_request("modulator_impulse.start", True),
                       lambda: self.runtime.set_ht_voltage(12.7, True),
                       lambda: self.runtime.outer_controlled_stop(True)):
            with self.assertRaises(RuntimeError):
                action()
        for bad in (True, 100, float("nan")):
            with self.assertRaises(ValueError):
                self.runtime.set_ht_voltage(bad, True)
        self.assertFalse(self.runtime.stage_request("modulator_impulse.start", True, False))
        self.assertEqual(self.backend.calls, [])

    def test_ht_command_and_outer_stop_execute_on_same_owner_without_release(self):
        self.runtime.set_ht_voltage(12.7, True)
        wait_state(self.runtime, "RUNNING")
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()
        self.runtime.outer_controlled_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual([row[0] for row in self.backend.calls], [("HT", 12.7), "outer.stop"])
        self.assertEqual(len({row[1] for row in self.backend.calls}), 1)
        self.assertNotEqual(self.backend.calls[0][1], threading.current_thread().ident)
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertEqual(self.backend.close_calls, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.request_shutdown()

    def test_impulsion_requires_stop_ack_even_after_legacy_general_arret(self):
        self.runtime.stage_request("modulator_impulse.start", True)
        wait_state(self.runtime, "RUNNING")
        self.assertTrue(self.runtime.snapshot()["pulse_stop_required"])
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertTrue(self.runtime.snapshot()["pulse_stop_required"])
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()
        self.runtime.stage_request("modulator_impulse.stop", True)
        wait_state(self.runtime, "RUNNING")
        self.assertFalse(self.runtime.snapshot()["pulse_stop_required"])

    def test_outer_stop_cannot_be_cancelled_by_cleanup_or_another_stop(self):
        self.backend.entered.clear()
        self.backend.release.clear()
        self.runtime.outer_controlled_stop(True)
        self.assertTrue(self.backend.entered.wait(1))
        for action in (lambda: self.runtime.deinitialize(True),
                       lambda: self.runtime.request_shutdown(True), lambda: self.runtime.general_stop(True),
                       lambda: self.runtime.outer_controlled_stop(True)):
            with self.assertRaises(RuntimeError):
                action()
        self.assertEqual(self.backend.close_calls, 0)
        self.backend.release.set()
        wait_state(self.runtime, "RUNNING")

    def test_failure_does_not_release_owner_or_reset_demanded_ht_stop(self):
        self.backend.fail_control = True
        self.runtime.set_ht_voltage(12.7, True)
        wait_state(self.runtime, "FAULT")
        self.assertTrue(self.runtime.snapshot()["ht_supply_stop_required"])
        self.assertTrue(self.backend.active)
        self.assertEqual(self.backend.close_calls, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()

    def test_failed_inflight_ht_cannot_erase_queued_outer_stop_or_allow_close(self):
        ht_entered, ht_release = threading.Event(), threading.Event()
        stop_entered, stop_release = threading.Event(), threading.Event()

        def failed_ht(*args, **kwargs):
            ht_entered.set()
            ht_release.wait(2)
            raise RuntimeError("HT write failed while outer stop was queued")

        def blocked_stop(*args, **kwargs):
            stop_entered.set()
            stop_release.wait(2)

        self.backend.set_ht_voltage = failed_ht
        self.backend.outer_controlled_stop = blocked_stop
        try:
            self.runtime.set_ht_voltage(12.7, True)
            self.assertTrue(ht_entered.wait(1))
            self.runtime.outer_controlled_stop(True)
            ht_release.set()
            self.assertTrue(stop_entered.wait(1))
            self.assertEqual(self.runtime.snapshot()["current_operation"], "acq.outer.controlled_stop")
            self.assertEqual(self.runtime.snapshot()["state"], "EXECUTING")
            for action in (lambda: self.runtime.deinitialize(True),
                           lambda: self.runtime.request_shutdown(True)):
                with self.assertRaises(RuntimeError):
                    action()
            self.assertEqual(self.backend.close_calls, 0)
        finally:
            ht_release.set()
            stop_release.set()
        wait_state(self.runtime, "RUNNING")


if __name__ == "__main__":
    unittest.main()
