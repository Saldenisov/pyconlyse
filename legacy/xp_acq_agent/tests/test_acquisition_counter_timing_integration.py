"""Source timing integration with injected owners only, compatible with 3.4."""
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend, DemoBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.tests.test_acquisition_source_controls import (
    Cancel, RuntimeBackend, backend_fixture,
)
from legacy.xp_acq_agent.tests.test_acquisition_runtime import wait_state


def bank(selector=1.0):
    return tuple(float(i) + .025 for i in range(32)) + (selector,)


def fixture(**flags):
    flags.setdefault("counter_timing_controls_verified", True)
    backend, owner, waits = backend_fixture(**flags)
    for number in range(8):
        if number not in owner.counter_channels:
            owner.counter_channels[number] = SimpleNamespace(co_pulse_done=True)
            owner.tasks["C10_NI6602_CO_{0}".format(number)] = Mock()
    return backend, owner, waits


class CounterTimingBackendTests(unittest.TestCase):
    def test_gate_is_independent_exact_boolean_and_demo_cannot_qualify(self):
        backend, owner, _ = fixture(counter_timing_controls_verified=False)
        with self.assertRaises(RuntimeError):
            backend.configure_counter_timing(bank(), Cancel(), True)
        self.assertIsNone(backend._counter_timing_bank)
        owner.stop_counter.assert_not_called()
        owner.write_counter_ticks.assert_not_called()
        self.assertFalse(backend.configure_counter_timing(bank(0.0), Cancel(), True))
        for value in (1, "yes", None):
            with self.assertRaises(ValueError):
                CardBackend(counter_timing_controls_verified=value)
        with self.assertRaises(ValueError):
            DemoBackend(counter_timing_controls_verified=True)

    def test_all_sixteen_selectors_reuse_correct_c10_task_and_preserve_other_fields(self):
        for selector in range(1, 17):
            backend, owner, _ = fixture()
            supplied = bank(float(selector))
            result = backend.configure_counter_timing(supplied, Cancel(), True)
            q = (selector - 1) // 2
            owner.stop_counter.assert_called_once_with(q)
            owner.start_counter.assert_called_once_with(q)
            self.assertEqual(owner.write_counter_ticks.call_args[0][0], q)
            self.assertEqual(backend._counter_timing_bank, supplied[:32] + (-1.0,))
            self.assertEqual(backend.counter_timing_publication["values"], backend._counter_timing_bank)
            self.assertFalse(backend.counter_timing_publication["psp_delivered"])
            self.assertFalse(result["hardware_acknowledged"])
            self.assertIn(q, backend.started_counters)
            self.assertEqual(backend._counter_configuration_uncertain, set())
            self.assertEqual(backend._pending_counter_stops, set())
            owner.update_counter_microseconds.assert_not_called()
            backend.factory.assert_called_once_with(authorized=True, outputs_commissioned=True)
            owner.close.assert_not_called()

    def test_poll_keeps_final_wait_and_source_signed_coercion_not_manual_conversion(self):
        backend, owner, _ = fixture()
        owner.read_counter_pulse_done.return_value = False
        owner.read_counter_pulse_done.side_effect = None
        supplied = (-.025, .125) + bank()[2:]
        cancel = Cancel()
        result = backend.configure_counter_timing(supplied, cancel, True)
        self.assertEqual(result["poll_iterations"], 22)
        self.assertEqual(cancel.waits, [.001] * 22)
        owner.write_counter_ticks.assert_called_once_with(0, 0, 0, 2)

    def test_confirmed_fractional_indices_reach_only_the_source_selected_counter(self):
        for selector, q in ((1.5, 0), (2.5, 0), (3.1, 1), (15.9, 7), (16.9, 7)):
            backend, owner, _ = fixture()
            result = backend.configure_counter_timing(bank(selector), Cancel(), True)
            owner.start_counter.assert_called_once_with(q)
            owner.stop_counter.assert_called_once_with(q)
            self.assertEqual(result["selector"], selector)
            self.assertEqual(owner.write_counter_ticks.call_args[0][0], q)
            owner.close.assert_not_called()

    def test_invalid_snapshot_and_confirmation_fail_before_io_or_command_image_change(self):
        backend, owner, _ = fixture()
        bad = (list(bank()), bank()[:-1], bank(.5), bank(True),
               bank()[:4] + (float("nan"),) + bank()[5:])
        for value in bad:
            with self.assertRaises(ValueError):
                backend.configure_counter_timing(value, Cancel(), True)
        with self.assertRaises(ValueError):
            backend.configure_counter_timing(bank(), Cancel(), 1)
        self.assertIsNone(backend._counter_timing_bank)
        owner.read_counter_pulse_done.assert_not_called()
        owner.stop_counter.assert_not_called()
        owner.write_counter_ticks.assert_not_called()

    def test_partial_property_write_keeps_prior_ack_image_and_blocks_new_energy(self):
        backend, owner, _ = fixture()
        backend.configure_counter_timing(bank(), Cancel(), True)
        old = dict(backend.commanded_counter_ticks[0])
        physical = {}

        def partial(number, initial, low, high):
            physical[number] = initial
            raise RuntimeError("initial delay applied; low/high acknowledgement lost")

        owner.write_counter_ticks.side_effect = partial
        changed = (100.0,) + bank()[1:]
        with self.assertRaises(Exception):
            backend.configure_counter_timing(changed, Cancel(), True)
        self.assertEqual(physical[0], 2000)
        self.assertEqual(backend.commanded_counter_ticks[0], old)
        self.assertEqual(backend._counter_configuration_uncertain, {0})
        self.assertFalse(backend.last_counter_timing["configuration_completed"])
        self.assertEqual(backend._counter_timing_bank, changed)  # Request, not an ACK.
        for action in (lambda: backend.configure_counter_timing(bank(), Cancel(), True),
                       lambda: backend.execute_impulsion("modulator_impulse.start", Cancel(), True),
                       lambda: backend.set_ht_voltage(6.0, Cancel(), True),
                       lambda: backend.execute_stage("chauffage.start", Cancel(), True),
                       lambda: backend.general_start(Cancel(), True)):
            with self.assertRaises(RuntimeError):
                action()
        self.assertEqual(owner.start_counter.call_count, 1)  # Earlier successful request only.
        self.assertEqual(owner.write_counter_ticks.call_count, 2)
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_failed_restart_retains_pending_stop_and_never_replays_properties(self):
        backend, owner, _ = fixture()
        owner.start_counter.side_effect = RuntimeError("start applied or not")
        with self.assertRaises(Exception):
            backend.configure_counter_timing(bank(13.0), Cancel(), True)
        self.assertEqual(backend._pending_counter_stops, {6})
        self.assertEqual(backend._counter_configuration_uncertain, set())
        self.assertEqual(backend._counter_timing_bank[32], 13.0)
        self.assertIsNone(backend.counter_timing_publication)
        self.assertEqual(owner.write_counter_ticks.call_count, 1)
        owner.close.assert_not_called()


class TimingRuntimeBackend(RuntimeBackend):
    def __init__(self):
        RuntimeBackend.__init__(self)
        self.counter_timing_controls_verified = True

    def configure_counter_timing(self, snapshot, cancel, operator_confirmed=False):
        self.record(("timing", snapshot))


class CounterTimingRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.backend = TimingRuntimeBackend()
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

    def test_default_disabled_and_bad_bank_never_queue_an_effect(self):
        self.backend.counter_timing_controls_verified = False
        before = self.runtime.snapshot()["state_revision"]
        with self.assertRaises(RuntimeError):
            self.runtime.configure_counter_timing(bank(), True)
        with self.assertRaises(ValueError):
            self.runtime.configure_counter_timing(bank(.5), True)
        self.assertFalse(self.runtime.configure_counter_timing(bank(17.0), True))
        self.assertEqual(self.runtime.snapshot()["state_revision"], before)
        self.assertEqual(self.backend.calls, [])

    def test_single_owner_and_non_modulator_counter_not_released_by_general_or_outer(self):
        self.runtime.configure_counter_timing(bank(13.0), True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])
        self.assertNotEqual(self.backend.calls[0][1], threading.current_thread().ident)
        self.runtime.general_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()
        self.runtime.outer_controlled_stop(True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])
        self.assertEqual(self.backend.close_calls, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.request_shutdown()

    def test_dedicated_impulsion_stop_ack_clears_only_retimed_three_and_four(self):
        for selector in (7.0, 9.0, 13.0):
            self.runtime.configure_counter_timing(bank(selector), True)
            wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [3, 4, 6])
        self.runtime.stage_request("modulator_impulse.stop", True)
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])

    def test_fractional_selector_release_latch_uses_source_quotient(self):
        for selector, required in ((2.9, [0]), (3.1, [0, 1]), (16.9, [0, 1, 7])):
            self.runtime.configure_counter_timing(bank(selector), True)
            wait_state(self.runtime, "RUNNING")
            self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], required)
        self.assertTrue(all(call[0][0] == "timing" for call in self.backend.calls))
        self.assertEqual([call[0][1][32] for call in self.backend.calls], [2.9, 3.1, 16.9])

    def test_invalid_fractional_task_never_changes_runtime_or_latch(self):
        revision = self.runtime.snapshot()["state_revision"]
        for selector in (5e-324, 0.1, 0.9999999999999999):
            with self.assertRaises(ValueError):
                self.runtime.configure_counter_timing(bank(selector), True)
        self.assertEqual(self.runtime.snapshot()["state_revision"], revision)
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [])
        self.assertEqual(self.backend.calls, [])

    def test_fault_retains_counter_requirement_and_owner(self):
        self.backend.fail_control = True
        self.runtime.configure_counter_timing(bank(5.0), True)
        wait_state(self.runtime, "FAULT")
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [2])
        self.assertEqual(self.backend.close_calls, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize()

    def test_queued_general_stop_does_not_overlap_timing_or_forget_other_counter(self):
        self.backend.entered.clear()
        self.backend.release.clear()
        self.runtime.configure_counter_timing(bank(13.0), True)
        self.assertTrue(self.backend.entered.wait(1))
        self.runtime.general_stop(True)
        self.assertEqual(len(self.backend.calls), 1)
        with self.assertRaises(RuntimeError):
            self.runtime.deinitialize(True)
        self.backend.release.set()
        wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.backend.calls[1][0], "general.stop")
        self.assertEqual(self.backend.calls[0][1], self.backend.calls[1][1])
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])
        self.assertEqual(self.backend.close_calls, 0)

    def test_confirmed_close_waits_for_current_timing_callback_on_same_owner(self):
        self.backend.entered.clear()
        self.backend.release.clear()
        self.runtime.configure_counter_timing(bank(), True)
        self.assertTrue(self.backend.entered.wait(1))
        self.runtime.deinitialize(True)
        self.assertEqual(self.backend.close_calls, 0)
        self.backend.release.set()
        wait_state(self.runtime, "IDLE")
        self.assertEqual(self.backend.close_calls, 1)
        self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [])

    def test_inflight_read_fault_invalidates_queued_timing_without_output_or_close(self):
        entered, release = threading.Event(), threading.Event()

        def failed_read(cancel):
            entered.set()
            release.wait(2)
            raise RuntimeError("Synthetic read failed after timing request was admitted")

        self.backend.read_snapshot = failed_read
        self.backend.entered.clear()
        try:
            self.assertTrue(entered.wait(1))
            self.runtime.configure_counter_timing(bank(), True)
            release.set()
            wait_state(self.runtime, "FAULT")
            self.assertFalse(self.backend.entered.wait(.1))
            self.assertEqual(self.runtime.snapshot()["state"], "FAULT")
            self.assertEqual(self.backend.calls, [])
            self.assertEqual(self.backend.close_calls, 0)
            self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [])
            self.assertIn("Synthetic read failed after timing request was admitted",
                          self.runtime.snapshot()["error"])
        finally:
            release.set()

    def test_invalidated_request_preserves_an_older_counter_stop_requirement(self):
        self.runtime.configure_counter_timing(bank(13.0), True)
        wait_state(self.runtime, "RUNNING")
        entered, release = threading.Event(), threading.Event()

        def failed_read(cancel):
            entered.set()
            release.wait(2)
            raise RuntimeError("Original read failure with an older retimed counter")

        self.backend.read_snapshot = failed_read
        self.backend.entered.clear()
        try:
            self.assertTrue(entered.wait(1))
            self.runtime.configure_counter_timing(bank(13.0), True)
            release.set()
            wait_state(self.runtime, "FAULT")
            self.assertFalse(self.backend.entered.wait(.1))
            self.assertEqual(self.runtime.snapshot()["state"], "FAULT")
            self.assertEqual(len(self.backend.calls), 1)
            self.assertEqual(self.runtime.snapshot()["counter_timing_stop_required"], [6])
            self.assertIn("Original read failure with an older retimed counter",
                          self.runtime.snapshot()["error"])
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()
