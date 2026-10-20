"""Offline Python3.4 tests. All readings, tasks and feedback are synthetic."""

import copy
import threading
import unittest
from unittest.mock import Mock

from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_gui import AcquisitionWindow
from legacy.xp_acq_agent.elyse_agent.acquisition_ht_shutdown import (
    HT_SUPPLY_STOP_DPS,
    HT_SUPPLY_STOP_EPS,
    execute_ht_shutdown,
    execute_ht_supply_stop,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import GeneralStopError
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.tests import test_acquisition_runtime as runtime_tests
from legacy.xp_acq_agent.tests.test_acquisition_general_stop import Clock


def sample(voltage=0.0, on=False, age=0.0):
    return dict(voltage_kv=voltage, supply_on=on, age_seconds=age)


class HTShutdownTests(unittest.TestCase):
    def execute(self, command, readings, **options):
        clock, events = Clock(), []
        reads = iter(readings)

        def read():
            events.append(("read",))
            return next(reads)

        result = execute_ht_shutdown(
            command,
            read,
            lambda value: events.append(("lower", value)),
            lambda: events.append(("ht_stop",)),
            lambda: events.append(("pulse_stop",)),
            clock.wait,
            feedback_verified=True,
            clock=clock,
            **options
        )
        return result, events

    def test_measured_zero_skips_all_ramp_writes_even_with_nonzero_command(self):
        for command in (0.0, 6.5, 8.0, 12.7, 20.0):
            result, events = self.execute(command, [sample(), sample()])
            self.assertEqual(events, [("read",), ("pulse_stop",), ("read",)])
            self.assertEqual(result["ramp_steps"], 0)
            self.assertEqual(result["command_kv"], command)
            self.assertTrue(result["measured_zero_confirmed"])
            self.assertTrue(result["supply_off_confirmed"])
            self.assertFalse(result["physical_pulse_absence_independently_measured"])

    def test_zero_voltage_with_supply_on_still_requires_ht_stop_then_pulse_stop(self):
        result, events = self.execute(12.7, [sample(0.0, True), sample()])
        self.assertEqual(events, [("read",), ("ht_stop",), ("pulse_stop",), ("read",)])
        self.assertEqual(result["ramp_steps"], 0)

    def test_lower_command_below_8_is_never_raised(self):
        result, events = self.execute(6.5, [sample(6.5, True), sample()])
        self.assertNotIn("lower", [row[0] for row in events])
        self.assertEqual(result["command_kv"], 6.5)
        self.assertLess(events.index(("ht_stop",)), events.index(("pulse_stop",)))

    def test_nonzero_ramp_clamps_to_8_then_stops_supply_then_pulses(self):
        result, events = self.execute(
            8.15, [sample(8.15, True), sample(8.05, True), sample(8.0, True), sample()]
        )
        commands = [row[1] for row in events if row[0] == "lower"]
        self.assertEqual(len(commands), 2)
        self.assertAlmostEqual(commands[0], 8.05)
        self.assertEqual(commands[1], 8.0)
        self.assertTrue(all(a > b for a, b in zip([8.15] + commands, commands)))
        self.assertEqual(events[-3:], [("ht_stop",), ("pulse_stop",), ("read",)])
        self.assertEqual(result["ramp_steps"], 2)

    def test_fresh_zero_mid_ramp_immediately_stops_further_analog_writes(self):
        result, events = self.execute(
            12.7, [sample(12.7, True), sample(0.0, True), sample()]
        )
        self.assertEqual([row[0] for row in events].count("lower"), 1)
        self.assertEqual(result["ramp_steps"], 1)

    def test_already_off_supply_with_residual_voltage_waits_for_zero_without_ramp(self):
        result, events = self.execute(
            12.7, [sample(2.0, False), sample(0.5, False), sample()]
        )
        self.assertNotIn("lower", [row[0] for row in events])
        self.assertNotIn("ht_stop", [row[0] for row in events])
        self.assertEqual(result["ramp_steps"], 0)

    def test_unknown_feedback_never_becomes_an_off_ack(self):
        invalid = [
            sample(age=2.0),
            sample(age=-1),
            sample(age=float("nan")),
            sample(float("nan")),
            sample(float("inf")),
            sample(-0.1),
            dict(voltage_kv=0.0, supply_on=0, age_seconds=0.0),
        ]
        for value in invalid:
            with self.subTest(value=value):
                clock, supply, pulses, lower = Clock(), Mock(), Mock(), Mock()
                with self.assertRaises(GeneralStopError):
                    execute_ht_shutdown(
                        12.7,
                        Mock(side_effect=[value, sample()]),
                        lower,
                        supply,
                        pulses,
                        clock.wait,
                        True,
                        clock=clock,
                    )
                lower.assert_not_called()
                supply.assert_called_once_with()
                pulses.assert_called_once_with()

    def test_pre_stop_zero_snapshot_is_never_reused_for_post_stop_confirmation(self):
        clock = Clock()
        read = Mock(
            side_effect=[sample(), sample(1.0, False)] + [sample(1.0, False)] * 20
        )
        with self.assertRaises(GeneralStopError) as caught:
            execute_ht_shutdown(
                6.5,
                read,
                Mock(),
                Mock(),
                Mock(),
                clock.wait,
                True,
                timeout_seconds=0.2,
                clock=clock,
            )
        self.assertGreater(read.call_count, 1)
        self.assertIn("timeout", str(caught.exception))

    def test_supply_on_blocks_even_if_voltage_is_zero(self):
        clock = Clock()
        with self.assertRaises(GeneralStopError):
            execute_ht_shutdown(
                6.5,
                lambda: sample(0.0, True),
                Mock(),
                Mock(),
                Mock(),
                clock.wait,
                True,
                timeout_seconds=0.2,
                clock=clock,
            )

    def test_failed_pulse_ack_blocks_despite_zero_and_supply_off(self):
        clock = Clock()
        with self.assertRaises(GeneralStopError) as caught:
            execute_ht_shutdown(
                6.5,
                lambda: sample(),
                Mock(),
                Mock(),
                Mock(side_effect=RuntimeError("counter4 not stopped")),
                clock.wait,
                True,
                clock=clock,
            )
        self.assertIn("counter4 not stopped", str(caught.exception))

    def test_ramp_write_failure_still_attempts_both_dedicated_stops_and_retains_error(
        self,
    ):
        clock, supply, pulses = Clock(), Mock(), Mock()
        with self.assertRaises(GeneralStopError) as caught:
            execute_ht_shutdown(
                12.7,
                Mock(side_effect=[sample(12.7, True), sample()]),
                Mock(side_effect=RuntimeError("AO failure")),
                supply,
                pulses,
                clock.wait,
                True,
                clock=clock,
            )
        supply.assert_called_once_with()
        pulses.assert_called_once_with()
        self.assertIn("AO failure", str(caught.exception))

    def test_all_failure_causes_retained_and_later_general_not_permitted(self):
        clock = Clock()
        with self.assertRaises(GeneralStopError) as caught:
            execute_ht_shutdown(
                12.7,
                Mock(side_effect=RuntimeError("read failure")),
                Mock(),
                Mock(side_effect=RuntimeError("HT stop failure")),
                Mock(side_effect=RuntimeError("pulse stop failure")),
                clock.wait,
                True,
                clock=clock,
            )
        for text in ("read failure", "HT stop failure", "pulse stop failure"):
            self.assertIn(text, str(caught.exception))

    def test_unverified_feedback_and_invalid_parameters_are_cold_errors(self):
        callback = Mock()
        for options in (
            dict(feedback_verified=False),
            dict(feedback_verified="yes"),
            dict(feedback_verified=True, zero_tolerance_kv=float("nan")),
            dict(feedback_verified=True, zero_tolerance_kv=8.0),
            dict(feedback_verified=True, timeout_seconds=0),
        ):
            with self.assertRaises(ValueError):
                execute_ht_shutdown(
                    6.5, callback, callback, callback, callback, callback, **options
                )
            callback.assert_not_called()

    def test_default_zero_is_exact_and_nonzero_band_requires_explicit_policy(self):
        result, _events = self.execute(
            12.7, [sample(0.01), sample(-0.01)], zero_tolerance_kv=0.02
        )
        self.assertEqual(result["ramp_steps"], 0)
        clock = Clock()
        with self.assertRaises(GeneralStopError):
            execute_ht_shutdown(
                6.5,
                lambda: sample(0.01),
                Mock(),
                Mock(),
                Mock(),
                clock.wait,
                True,
                timeout_seconds=0.2,
                clock=clock,
            )

    def test_event21_release_is_retried_and_status_is_not_physical_ack(self):
        writes, status, waits = [], [], []

        def commit(line, value):
            writes.append((line, value))
            if len(writes) == 2:
                raise RuntimeError("release failed")

        with self.assertRaises(GeneralStopError):
            execute_ht_supply_stop(
                commit, lambda *args: status.append(args), waits.append
            )
        self.assertEqual(writes, [(19, False), (19, True), (19, True)])
        self.assertEqual(waits, [0.15, 0.1])
        self.assertEqual(status, [(HT_SUPPLY_STOP_EPS, HT_SUPPLY_STOP_DPS)])

    def test_observer_failure_does_not_skip_dedicated_stops_or_become_success(self):
        for failed_stage in (
            "stop_ht_supply",
            "stop_modulator_pulses",
            "ht_preamble_completed",
        ):
            with self.subTest(failed_stage=failed_stage):
                clock, supply, pulses = Clock(), Mock(), Mock()

                def observe(stage):
                    if stage == failed_stage:
                        raise RuntimeError("synthetic observer failure")

                with self.assertRaises(GeneralStopError):
                    execute_ht_shutdown(
                        6.5,
                        Mock(side_effect=[sample(0.0, True), sample()]),
                        Mock(),
                        supply,
                        pulses,
                        clock.wait,
                        True,
                        clock=clock,
                        observer=observe,
                    )
                supply.assert_called_once_with()
                pulses.assert_called_once_with()


class ExtendedStopBackendTests(unittest.TestCase):
    def backend(self, verified=True):
        owner = runtime_tests.BackendTests().fake_owner()
        for number in (3, 4):
            task = Mock()
            task.is_task_done.side_effect = AssertionError("TaskDone is not source CO PulseDone")
            owner.tasks["C10_NI6602_CO_{0}".format(number)] = task
        owner.read_counter_pulse_done.return_value = True
        owner.stop_counter.side_effect = lambda number: owner.tasks[
            "C10_NI6602_CO_{0}".format(number)].stop()
        backend = CardBackend(
            Mock(return_value=owner),
            focal_off=Mock(),
            stop_wait=lambda _seconds: None,
            control_profile="extended_ht_stop",
            ht_feedback_verified=verified,
        )
        backend.initialize(threading.Event(), startup_confirmed=True)
        return owner, backend

    def test_native_boundary_reads_C2_7_with_scale_2_44_and_C4_48(self):
        owner, backend = self.backend()
        raw, inputs = [0.0] * 64, [False] * 64
        raw[7], inputs[48] = 2.0, True
        owner.read_analog_means.return_value = raw
        owner.read_analog_means.side_effect = None
        owner.tasks["C4_DIO96_DI"].read.return_value = inputs
        result = backend._read_ht_shutdown_sample()
        self.assertAlmostEqual(result["voltage_kv"], 4.88)
        self.assertIs(result["supply_on"], False)
        self.assertIs(result["raw_supply_contact"], True)
        owner.tasks["C2_NI6071E_AI"].start.assert_called_once_with()
        owner.tasks["C2_NI6071E_AI"].stop.assert_called_once_with()

    def test_raw_low_ht_contact_means_supply_on_not_off(self):
        owner, backend = self.backend()
        owner.read_analog_means.side_effect = None
        owner.read_analog_means.return_value = [0.0] * 64
        owner.tasks["C4_DIO96_DI"].read.return_value = [False] * 64
        result = backend._read_ht_shutdown_sample()
        self.assertIs(result["supply_on"], True)
        self.assertIs(result["raw_supply_contact"], False)

    def test_zero_path_does_not_write_analog_and_checks_both_pulses_before_full_general(
        self,
    ):
        owner, backend = self.backend()
        backend._read_ht_shutdown_sample = Mock(side_effect=[sample(), sample()])
        events = []
        for number in (3, 4):
            owner.tasks["C10_NI6602_CO_{0}".format(number)].stop.side_effect = (
                lambda number=number: events.append(("pulse", number))
            )
        backend.focal_off.side_effect = lambda: events.append(("focal_off",))
        backend.general_stop(operator_confirmed=True)
        owner.write_analog_logical_bank.assert_not_called()
        self.assertEqual(events, [("pulse", 3), ("pulse", 4), ("focal_off",)])
        self.assertEqual([call[0] for call in owner.read_counter_pulse_done.call_args_list], [(3,), (4,)])
        self.assertEqual([call[0] for call in owner.stop_counter.call_args_list], [(3,), (4,)])
        for number in (3, 4):
            owner.tasks["C10_NI6602_CO_{0}".format(number)].is_task_done.assert_not_called()
        self.assertEqual(owner.write_digital_bank.call_count, 10)
        self.assertEqual(backend.commanded_analog["C9NI6703"][0], 6.5)
        self.assertEqual(backend.procedure["source_frames_attempted"], list(range(17)))
        self.assertTrue(backend.procedure["command_sequence_completed"])
        self.assertTrue(backend.procedure["ht_supply_stop_included"])
        self.assertEqual(backend.software_status_assignments["EPS"][42], True)
        self.assertNotIn(55, backend.software_status_assignments["EPS"])

    def test_ht_stop_precedes_both_counter_stops_then_original_general(self):
        owner, backend = self.backend()
        backend._read_ht_shutdown_sample = Mock(
            side_effect=[sample(0.0, True), sample()]
        )
        events = []
        owner.write_digital_bank.side_effect = lambda _name, values: events.append(
            ("C4_19", values[19])
        )
        for number in (3, 4):
            owner.tasks["C10_NI6602_CO_{0}".format(number)].stop.side_effect = (
                lambda number=number: events.append(("pulse", number))
            )
        backend.focal_off.side_effect = lambda: events.append(("focal_off",))
        backend.general_stop(operator_confirmed=True)
        self.assertEqual(
            events[:5],
            [
                ("C4_19", False),
                ("C4_19", True),
                ("pulse", 3),
                ("pulse", 4),
                ("focal_off",),
            ],
        )
        owner.write_analog_logical_bank.assert_not_called()

    def test_any_failed_pulse_still_stops_other_counter_but_never_stops_later_stages(
        self,
    ):
        owner, backend = self.backend()
        backend._read_ht_shutdown_sample = Mock(side_effect=[sample(), sample()])
        owner.tasks["C10_NI6602_CO_3"].stop.side_effect = RuntimeError(
            "counter3 stop failed"
        )
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        owner.tasks["C10_NI6602_CO_4"].stop.assert_called_once_with()
        backend.focal_off.assert_not_called()
        owner.write_digital_bank.assert_not_called()
        self.assertEqual(backend.procedure["source_frames_attempted"], [])
        self.assertFalse(backend.procedure["command_sequence_completed"])
        owner.close.assert_not_called()

    def test_invalid_ht_read_still_attempts_ht_and_pulse_stops_not_general(self):
        owner, backend = self.backend()
        backend._read_ht_shutdown_sample = Mock(side_effect=[sample(age=3), sample()])
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 2)
        for number in (3, 4):
            owner.tasks[
                "C10_NI6602_CO_{0}".format(number)
            ].stop.assert_called_once_with()
        backend.focal_off.assert_not_called()
        self.assertIs(backend.owner, owner)

    def test_counter_polls_bounded_and_done_error_still_stops_both(self):
        owner, backend = self.backend()
        def pulse_done(number):
            if number == 3:
                return False
            raise RuntimeError("Pulse-done query failure")
        owner.read_counter_pulse_done.side_effect = pulse_done
        with self.assertRaises(GeneralStopError):
            backend._stop_modulator_pulses(Mock())
        calls = [call[0][0] for call in owner.read_counter_pulse_done.call_args_list]
        self.assertEqual(calls, [3] * 42 + [4])
        self.assertEqual([call[0] for call in owner.stop_counter.call_args_list], [(3,), (4,)])
        for number in (3, 4):
            owner.tasks[
                "C10_NI6602_CO_{0}".format(number)
            ].stop.assert_called_once_with()
            owner.tasks["C10_NI6602_CO_{0}".format(number)].is_task_done.assert_not_called()

    def test_pulse_done_requires_exact_bool_without_task_done_fallback(self):
        for invalid in (None, 0, 1, "False", object()):
            owner, backend = self.backend()
            owner.read_counter_pulse_done.return_value = invalid
            with self.assertRaises(GeneralStopError) as caught:
                backend._stop_modulator_pulses(Mock())
            self.assertIn("Counter Done must be Boolean", str(caught.exception))
            self.assertEqual([call[0] for call in owner.stop_counter.call_args_list], [(3,), (4,)])
            for number in (3, 4):
                owner.tasks["C10_NI6602_CO_{0}".format(number)].is_task_done.assert_not_called()

    def test_missing_pulse_done_capability_retains_owner_and_attempts_both_stops(self):
        owner, backend = self.backend()
        del owner.read_counter_pulse_done
        with self.assertRaises(GeneralStopError):
            backend._stop_modulator_pulses(Mock())
        self.assertEqual([call[0] for call in owner.stop_counter.call_args_list], [(3,), (4,)])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_pulse_done_final_iteration_wait_precedes_each_owner_stop(self):
        owner, backend = self.backend()
        events = []
        owner.read_counter_pulse_done.side_effect = lambda number: events.append(("done", number)) or True
        owner.stop_counter.side_effect = lambda number: events.append(("stop", number))
        backend.stop_wait = lambda seconds: events.append(("wait", seconds))
        backend._stop_modulator_pulses(Mock())
        self.assertEqual(events, [("done", 3), ("wait", 0.001), ("stop", 3),
                                  ("done", 4), ("wait", 0.001), ("stop", 4), ("wait", 0.1)])

    def test_lowering_preserves_other_nine_AO_fields_and_updates_only_after_ack(self):
        owner, backend = self.backend()
        old = copy.deepcopy(backend.commanded_analog)
        backend._lower_ht_shutdown_command(6.4)
        name, values = owner.write_analog_logical_bank.call_args[0]
        self.assertEqual(name, "C9NI6703")
        self.assertEqual(tuple(values[1:]), old["C9NI6703"][1:])
        for forbidden in (6.4, 6.5, 8.0, float("nan")):
            with self.assertRaises(ValueError):
                backend._lower_ht_shutdown_command(forbidden)
        owner.write_analog_logical_bank.side_effect = RuntimeError("AO write failed")
        with self.assertRaises(RuntimeError):
            backend._lower_ht_shutdown_command(6.3)
        self.assertEqual(backend.commanded_analog["C9NI6703"][0], 6.4)
        owner.write_analog_logical_bank.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "Ambiguous C9 write"):
            backend._lower_ht_shutdown_command(6.2)
        owner.write_analog_logical_bank.assert_not_called()
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_unverified_profile_refuses_start_and_stop_before_any_output(self):
        owner, backend = self.backend(verified=False)
        for action in (
            lambda: backend.general_start(threading.Event(), True),
            lambda: backend.general_stop(True),
        ):
            with self.assertRaises(RuntimeError):
                action()
        owner.write_digital_bank.assert_not_called()
        owner.write_analog_logical_bank.assert_not_called()
        backend.focal_off.assert_not_called()

    def test_owner_thread_retains_tasks_after_ht_failure_and_allows_verified_retry(
        self,
    ):
        owner, backend = self.backend()
        backend.owner = None
        backend._read_ht_shutdown_sample = Mock(side_effect=[sample(age=3), sample()])
        runtime = AcquisitionRuntime(lambda: backend, period=0.02)
        runtime.start()
        try:
            runtime.initialize(True)
            runtime_tests.wait_state(runtime, "RUNNING")
            runtime.general_stop(True)
            runtime_tests.wait_state(runtime, "FAULT")
            self.assertTrue(runtime.snapshot()["general_stop_required"])
            with self.assertRaises(RuntimeError):
                runtime.deinitialize()
            owner.close.assert_not_called()
            backend._read_ht_shutdown_sample.side_effect = [sample(), sample()]
            runtime.general_stop(True)
            runtime_tests.wait_state(runtime, "RUNNING")
            self.assertFalse(runtime.snapshot()["general_stop_required"])
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(3))

    def test_gui_describes_zero_skip_and_does_not_execute_on_cancel(self):
        window = AcquisitionWindow.__new__(AcquisitionWindow)
        window.demo, window.general_only, window.extended_ht = False, False, True
        window.root, window.runtime, window.messagebox = Mock(), Mock(), Mock()
        window.messagebox.askyesno.return_value = False
        window.general_stop()
        window.runtime.general_stop.assert_not_called()
        text = window.messagebox.askyesno.call_args[0][1]
        for phrase in (
            "If already zero",
            "do not lower or raise",
            "counters3/4",
            "AND",
            "blocks",
        ):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
