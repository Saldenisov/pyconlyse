"""Offline Python-3.4 tests: injected callbacks, no NI/VISA/PSP or native DLL."""
import ctypes
import os
import subprocess
import threading
import time
import unittest
from unittest.mock import Mock, patch

from legacy.xp_acq_agent.elyse_agent.acquisition_procedures import (
    execute_general_stop, GeneralStopError, GENERAL_STOP_FRAMES,
    GENERAL_STOP_EPS, GENERAL_STOP_DPS, ProcedureCancelled,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_agent.elyse_agent.acquisition_runtime import AcquisitionRuntime
from legacy.xp_acq_agent.elyse_agent.acquisition_gui import AcquisitionWindow
from legacy.xp_acq_agent.elyse_agent import chroma_focal_stop as chroma
from legacy.xp_acq_agent.tests import test_acquisition_runtime as runtime_tests


class Clock(object):
    def __init__(self):
        self.now, self.waits = 0, []

    def __call__(self):
        return self.now

    def wait(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


class GeneralStopTests(unittest.TestCase):
    def test_exact_17_frames_five_active_low_pulses_and_parallel_first_wait(self):
        clock, writes, frames, status = Clock(), [], [], []
        focal = Mock(side_effect=lambda: setattr(clock, "now", clock.now + .25))
        execute_general_stop(lambda *row: writes.append(row), focal,
                             lambda *row: status.append(row), clock.wait,
                             lambda *row: frames.append(row), True, clock)
        self.assertEqual(writes, [(line, state) for line in (8, 17, 6, 4, 1) for state in (False, True)])
        self.assertEqual(frames, [(row[0], row[1]) for row in GENERAL_STOP_FRAMES])
        self.assertEqual(status, [(GENERAL_STOP_EPS, GENERAL_STOP_DPS)])
        self.assertEqual(clock.waits, [.5, .15, 1, .15, 1, .15, 1, .15, 2, .15, .1])
        self.assertAlmostEqual(clock.now, 6.6)
        focal.assert_called_once_with()

    def test_confirmation_is_required_before_any_callback(self):
        callback = Mock()
        with self.assertRaises(ValueError):
            execute_general_stop(callback, callback, callback, callback)
        callback.assert_not_called()

    def test_focal_failure_does_not_skip_remaining_stop_stages(self):
        clock, writes = Clock(), []
        with self.assertRaises(GeneralStopError) as caught:
            execute_general_stop(lambda *row: writes.append(row),
                                 Mock(side_effect=RuntimeError("focal offline")), Mock(),
                                 clock.wait, operator_confirmed=True, clock=clock)
        self.assertEqual(len(writes), 10)
        self.assertEqual(writes[-2:], [(1, False), (1, True)])
        self.assertIn("focal offline", str(caught.exception))

    def test_failed_assertion_and_release_are_reported_and_all_restores_attempted(self):
        clock, writes = Clock(), []
        def commit(line, value):
            writes.append((line, value))
            if line in (8, 17):
                raise RuntimeError("synthetic partial write")
        with self.assertRaises(GeneralStopError) as caught:
            execute_general_stop(commit, lambda: None, Mock(), clock.wait,
                                 operator_confirmed=True, clock=clock)
        self.assertIn((1, False), writes)
        self.assertEqual(writes[-2:], [(8, True), (17, True)])
        self.assertEqual(len(caught.exception.failures), 6)

    def test_wait_failure_does_not_abort_remaining_stop(self):
        writes = []
        with self.assertRaises(GeneralStopError):
            execute_general_stop(lambda *row: writes.append(row), lambda: None, Mock(),
                                 Mock(side_effect=RuntimeError("synthetic wait failure")),
                                 operator_confirmed=True)
        self.assertEqual(len(writes), 10)

    def backend(self, focal):
        owner = runtime_tests.BackendTests().fake_owner()
        backend = CardBackend(Mock(return_value=owner), focal_off=focal, stop_wait=lambda _: None)
        backend.initialize(threading.Event(), startup_confirmed=True)
        return owner, backend

    def test_backend_preserves_unrelated_bits_and_retains_tasks(self):
        owner, backend = self.backend(lambda: None)
        startup = tuple(backend.commanded_digital["C4_DIO96_DO"])
        backend.general_stop(operator_confirmed=True)
        self.assertEqual(owner.write_digital_bank.call_count, 10)
        for call in owner.write_digital_bank.call_args_list:
            bank = call[0][1]
            self.assertTrue(all(bank[i] == startup[i] for i in range(32) if i not in (8, 17, 6, 4, 1)))
        self.assertEqual(backend.initial_images["digital"]["C4_DIO96_DO"], startup)
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()
        self.assertEqual(backend.software_status_assignments["EPS"], dict(GENERAL_STOP_EPS))
        self.assertEqual(backend.procedure["frame"], 16)
        self.assertFalse(backend.procedure["hardware_off_confirmed"])

    def test_backend_records_partial_failure_not_software_success(self):
        owner, backend = self.backend(Mock(side_effect=RuntimeError("unverified mapping")))
        with self.assertRaises(GeneralStopError):
            backend.general_stop(operator_confirmed=True)
        self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
        self.assertIn("unverified mapping", backend.procedure["failures"][0])
        owner.close.assert_not_called()

    def test_default_chroma_adapter_blocks_marche_before_first_output_write(self):
        owner, backend = self.backend(chroma.ChromaFocalStop())
        with self.assertRaises(RuntimeError):
            backend.general_start(threading.Event(), operator_confirmed=True)
        owner.write_digital_bank.assert_not_called()


class StopRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.backend = runtime_tests.FakeBackend()
        self.runtime = AcquisitionRuntime(lambda: self.backend, period=.02)
        self.runtime.start()
        self.runtime.initialize(startup_confirmed=True)
        runtime_tests.wait_state(self.runtime, "RUNNING")

    def tearDown(self):
        self.runtime.request_shutdown(electrical_off_confirmed=True)
        self.assertTrue(self.runtime.join(3))

    def test_stop_preempts_start_on_same_owner_without_reinitializing(self):
        entered, stopped = threading.Event(), threading.Event()
        calls = []
        def start(cancel, operator_confirmed=False):
            entered.set()
            cancel.wait(1)
            calls.append("restore start pulse")
            raise ProcedureCancelled()
        def stop(operator_confirmed=False):
            self.assertTrue(operator_confirmed)
            self.assertEqual(threading.current_thread().name, "ACQ-card-owner")
            self.assertEqual(self.backend.close_calls, 0)
            calls.append("stop")
            stopped.set()
        self.backend.general_start, self.backend.general_stop = start, stop
        self.runtime.general_start(operator_confirmed=True)
        self.assertTrue(entered.wait(1))
        self.runtime.general_stop(operator_confirmed=True)
        self.assertTrue(stopped.wait(1))
        runtime_tests.wait_state(self.runtime, "RUNNING")
        self.assertEqual(calls, ["restore start pulse", "stop"])
        self.assertFalse(self.runtime.snapshot()["general_stop_required"])
        self.runtime.deinitialize()
        runtime_tests.wait_state(self.runtime, "IDLE")

    def test_partial_stop_retains_owner_blocks_release_and_allows_retry(self):
        self.backend.general_stop = Mock(side_effect=GeneralStopError(["focal offline"]))
        self.runtime.general_stop(operator_confirmed=True)
        runtime_tests.wait_state(self.runtime, "FAULT")
        self.assertEqual(self.backend.close_calls, 0)
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])
        for action in (self.runtime.deinitialize, self.runtime.request_shutdown):
            with self.assertRaises(RuntimeError):
                action()
        self.backend.general_stop.side_effect = None
        self.runtime.general_stop(operator_confirmed=True)
        runtime_tests.wait_state(self.runtime, "RUNNING")
        self.assertEqual(self.backend.general_stop.call_count, 2)

    def test_close_cannot_interrupt_stop_even_with_local_off_ack(self):
        entered, release = threading.Event(), threading.Event()
        def stop(operator_confirmed=False):
            entered.set()
            release.wait(1)
        self.backend.general_stop = stop
        self.runtime.general_stop(operator_confirmed=True)
        try:
            self.assertTrue(entered.wait(1))
            for action in (self.runtime.deinitialize, self.runtime.request_shutdown):
                with self.assertRaises(RuntimeError):
                    action(electrical_off_confirmed=True)
            self.assertEqual(self.backend.close_calls, 0)
        finally:
            release.set()
            runtime_tests.wait_state(self.runtime, "RUNNING")

    def test_failed_start_does_not_release_card_owner(self):
        self.backend.general_start = Mock(side_effect=RuntimeError("partial start write"))
        self.runtime.general_start(operator_confirmed=True)
        runtime_tests.wait_state(self.runtime, "FAULT")
        self.assertEqual(self.backend.close_calls, 0)
        self.assertTrue(self.runtime.snapshot()["general_stop_required"])

    def test_read_fault_after_marche_does_not_silently_release_live_outputs(self):
        self.backend.general_start = Mock()
        self.runtime.general_start(operator_confirmed=True)
        runtime_tests.wait_state(self.runtime, "RUNNING")
        self.backend.fail_read = True
        runtime_tests.wait_state(self.runtime, "FAULT")
        self.assertEqual(self.backend.close_calls, 0)
        self.assertEqual(self.runtime.snapshot()["resource_count"], 2)
        self.assertTrue(self.runtime.snapshot()["stale"])

    def test_stop_interrupts_input_read_without_concurrent_close(self):
        entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
        self.backend.read_entered, self.backend.release_read = entered, release
        self.backend.general_stop = lambda operator_confirmed=False: stopped.set()
        self.assertTrue(entered.wait(1))
        self.runtime.general_stop(operator_confirmed=True)
        time.sleep(.03)
        self.assertFalse(stopped.is_set())
        self.assertEqual(self.backend.close_calls, 0)
        release.set()
        self.assertTrue(stopped.wait(1))
        runtime_tests.wait_state(self.runtime, "RUNNING")

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):
            self.runtime.general_stop()


class FullGeneralStopIntegrationTests(unittest.TestCase):
    """Real backend/runtime code with synthetic owner, DLL and GUI boundaries."""
    def backend(self, focal=None):
        owner = runtime_tests.BackendTests().fake_owner()
        focal = focal if focal is not None else Mock()
        backend = CardBackend(Mock(return_value=owner), focal_off=focal,
                              stop_wait=lambda _seconds: None, control_profile="legacy_full")
        backend.initialize(threading.Event(), startup_confirmed=True)
        return owner, backend, focal

    def test_full_profile_reaches_all_source_frames_and_names_unproven_physical_state(self):
        owner, backend, focal = self.backend()
        backend.general_stop(operator_confirmed=True)
        result = backend.procedure
        self.assertEqual(result["stop_scope"], "labview_event_6")
        self.assertEqual(result["source_frames_attempted"], list(range(17)))
        self.assertTrue(result["command_sequence_completed"])
        self.assertFalse(result["hardware_off_confirmed"])
        self.assertFalse(result["ht_supply_stop_included"])
        self.assertTrue(result["source_psp_write_replaced_by_ram_status"])
        self.assertEqual(result["requested_stop_stages"], [
            "chroma_focales", "focale_klystron", "relais_ht", "premagnetisation", "chauffage", "general"])
        self.assertEqual(result["failures"], [])
        focal.assert_called_once_with()
        self.assertEqual(owner.write_digital_bank.call_count, 10)
        owner.close.assert_not_called()

    def test_full_stop_restores_interrupted_start_and_never_reasserts_it(self):
        owner, backend, focal = self.backend()
        image = list(backend.commanded_digital["C4_DIO96_DO"])
        image[0] = image[2] = True
        backend.commanded_digital["C4_DIO96_DO"] = image
        backend.general_stop(operator_confirmed=True)
        writes = [call[0][1] for call in owner.write_digital_bank.call_args_list]
        self.assertEqual(len(writes), 11)  # restore both pulses, then ten source writes
        self.assertTrue(all(row[0] is False and row[2] is False for row in writes))
        self.assertEqual(writes[-1], list(backend.initial_images["digital"]["C4_DIO96_DO"]))
        focal.assert_called_once_with()

    def test_restore_failure_cannot_skip_focal_or_any_of_the_17_frames(self):
        owner, backend, focal = self.backend()
        image = list(backend.commanded_digital["C4_DIO96_DO"])
        image[0] = True
        backend.commanded_digital["C4_DIO96_DO"] = image
        owner.write_digital_bank.side_effect = [RuntimeError("restore failed")] + [None] * 10
        with self.assertRaises(GeneralStopError) as caught:
            backend.general_stop(operator_confirmed=True)
        self.assertIn("restore C4[0]=False", str(caught.exception))
        self.assertEqual(owner.write_digital_bank.call_count, 11)
        self.assertTrue(all(call[0][1][0] is False for call in owner.write_digital_bank.call_args_list))
        self.assertEqual(backend.procedure["source_frames_attempted"], list(range(17)))
        self.assertFalse(backend.procedure["command_sequence_completed"])
        self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
        focal.assert_called_once_with()
        owner.close.assert_not_called()

    def test_restore_focal_and_ni_failures_are_all_retained(self):
        owner, backend, _focal = self.backend(Mock(side_effect=RuntimeError("focal blocked")))
        image = list(backend.commanded_digital["C4_DIO96_DO"])
        image[0] = True
        backend.commanded_digital["C4_DIO96_DO"] = image
        owner.write_digital_bank.side_effect = [RuntimeError("restore failed"),
                                               RuntimeError("focal pulse failed")] + [None] * 9
        with self.assertRaises(GeneralStopError) as caught:
            backend.general_stop(operator_confirmed=True)
        for text in ("restore failed", "focal blocked", "focal pulse failed"):
            self.assertIn(text, str(caught.exception))
        self.assertEqual(backend.procedure["source_frames_attempted"], list(range(17)))
        self.assertFalse(backend.procedure["command_sequence_completed"])
        self.assertIs(backend.owner, owner)
        owner.close.assert_not_called()

    def test_each_of_ten_ni_write_failures_still_attempts_later_stages_and_reports_fault(self):
        for failed_call in range(10):
            with self.subTest(failed_call=failed_call):
                owner, backend, focal = self.backend()
                def fail_once(_name, _values):
                    if owner.write_digital_bank.call_count == failed_call + 1:
                        raise RuntimeError("synthetic NI write failure")
                owner.write_digital_bank.side_effect = fail_once
                with self.assertRaises(GeneralStopError):
                    backend.general_stop(operator_confirmed=True)
                self.assertEqual(owner.write_digital_bank.call_count, 10 + (failed_call % 2))
                self.assertEqual(backend.procedure["source_frames_attempted"], list(range(17)))
                self.assertFalse(backend.procedure["command_sequence_completed"])
                self.assertFalse(backend.procedure["hardware_off_confirmed"])
                self.assertEqual(backend.procedure["state"], "PARTIAL_STOP_FAILURE")
                self.assertEqual(backend.commanded_digital["C4_DIO96_DO"],
                                 backend.initial_images["digital"]["C4_DIO96_DO"])
                focal.assert_called_once_with()
                owner.close.assert_not_called()

    def test_wait_and_observer_failures_do_not_gate_any_stop_write(self):
        writes, frames = [], []
        def observer(index, uid):
            frames.append(index)
            raise RuntimeError("synthetic observer failure")
        with self.assertRaises(GeneralStopError) as caught:
            execute_general_stop(lambda *row: writes.append(row), lambda: None, Mock(),
                                 Mock(side_effect=RuntimeError("synthetic wait failure")),
                                 observer, operator_confirmed=True)
        self.assertEqual(writes, [(line, state) for line in (8, 17, 6, 4, 1) for state in (False, True)])
        self.assertEqual(frames, list(range(17)))
        self.assertIn("observer failure", str(caught.exception))
        self.assertIn("wait failure", str(caught.exception))

    def test_full_stop_can_run_without_any_general_marche_or_other_stage_start(self):
        owner, backend, focal = self.backend()
        startup = list(backend.commanded_digital["C4_DIO96_DO"])
        backend.general_stop(operator_confirmed=True)
        # Only the reviewed active-low stop bits may differ from startup.
        for call in owner.write_digital_bank.call_args_list:
            name, values = call[0]
            self.assertEqual(name, "C4_DIO96_DO")
            self.assertEqual(len(values), 32)
            self.assertTrue(all(value == startup[i] for i, value in enumerate(values)
                                if i not in (8, 17, 6, 4, 1)))
        owner.write_initial_images.assert_called_once_with()
        owner.start_legacy_counters.assert_called_once_with()
        self.assertEqual(backend.software_status_assignments, {
            "EPS": dict(GENERAL_STOP_EPS), "DPS": dict(GENERAL_STOP_DPS)})

    def test_real_backend_and_owner_thread_full_stop_failure_retry_then_cleanup(self):
        owner, backend, focal = self.backend(Mock(side_effect=RuntimeError("unverified Chroma")))
        backend.owner = None  # runtime performs the initialization itself
        factory = Mock(return_value=backend)
        calls = []
        owner.write_digital_bank.side_effect = lambda *_args: calls.append(threading.current_thread().name)
        runtime = AcquisitionRuntime(factory, period=.02)
        runtime.start()
        try:
            runtime.initialize(startup_confirmed=True)
            runtime_tests.wait_state(runtime, "RUNNING")
            runtime.general_stop(operator_confirmed=True)
            runtime_tests.wait_state(runtime, "FAULT")
            result = runtime.snapshot()
            self.assertTrue(result["general_stop_required"])
            self.assertTrue(result["stale"])
            self.assertEqual(result["procedure"]["frame"], 16)
            self.assertEqual(result["resource_count"], len(owner.tasks))
            self.assertFalse(result["procedure"]["command_sequence_completed"])
            for release in (runtime.deinitialize, runtime.request_shutdown):
                with self.assertRaises(RuntimeError):
                    release()
            owner.close.assert_not_called()
            focal.side_effect = None
            runtime.general_stop(operator_confirmed=True)
            runtime_tests.wait_state(runtime, "RUNNING")
            self.assertFalse(runtime.snapshot()["general_stop_required"])
            self.assertTrue(runtime.snapshot()["procedure"]["command_sequence_completed"])
            self.assertEqual(len(calls), 20)
            self.assertEqual(set(calls), set(("ACQ-card-owner",)))
            factory.assert_called_once_with()
            owner.close.assert_not_called()
            runtime.deinitialize()
            runtime_tests.wait_state(runtime, "IDLE")
            self.assertEqual(runtime.snapshot()["resource_count"], 0)
        finally:
            runtime.request_shutdown(electrical_off_confirmed=True)
            self.assertTrue(runtime.join(3))

    def test_full_gui_confirmation_is_cancellable_and_states_ht_supply_boundary(self):
        window = AcquisitionWindow.__new__(AcquisitionWindow)
        window.demo, window.general_only = False, False
        window.root, window.runtime, window.messagebox = Mock(), Mock(), Mock()
        window.messagebox.askyesno.return_value = False
        window.general_stop()
        window.runtime.general_stop.assert_not_called()
        message = window.messagebox.askyesno.call_args[0][1]
        for text in ("Original ACQ event 6", "C4[8], C4[17], C4[6], C4[4], C4[1]",
                     "Chroma", "Does NOT issue separate alimentation HT stop C4[19]",
                     "partial failure", "NOT an emergency stop"):
            self.assertIn(text, message)
        window.messagebox.askyesno.return_value = True
        window.general_stop()
        window.runtime.general_stop.assert_called_once_with(operator_confirmed=True)


class ChromaStopTests(unittest.TestCase):
    def fake_dll(self, fail=None):
        dll, calls = Mock(), []
        for name in ("init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close"):
            function = getattr(dll, "chr62000_" + name)
            def invoke(*args, **kwargs):
                name = kwargs["name"]
                calls.append((name, args))
                if name == "init":
                    args[3]._obj.value = 123
                return -7 if name == fail else 0
            # Avoid keyword-only syntax in the production module; tests also
            # run on the real 3.4 interpreter.
            function.side_effect = lambda *args, **kw: None
            def bind(label):
                return lambda *args: invoke(*args, name=label)
            function.side_effect = bind(name)
        return dll, calls

    def test_saved_three_off_chains_no_output_on_call(self):
        for branch in chroma.BRANCHES:
            dll, calls = self.fake_dll()
            chroma.run_branch(dll, branch)
            self.assertEqual([row[0] for row in calls],
                             ["init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close"])
            self.assertEqual(calls[0][1][:3], (branch[1].encode("ascii"), 0, 1))
            self.assertEqual([calls[i][1][1] for i in (1, 2, 3)], list(branch[2:]))
            self.assertEqual(calls[4][1], (123, 0))
            self.assertEqual(dll.chr62000_SetOutput.argtypes, [ctypes.c_uint32, ctypes.c_uint16])

    def test_prior_setpoint_error_skips_later_commands_but_closes_session(self):
        dll, calls = self.fake_dll("SetVoltage")
        with self.assertRaises(RuntimeError):
            chroma.run_branch(dll, chroma.BRANCHES[0])
        self.assertEqual([row[0] for row in calls], ["init", "SetVoltage", "close"])

    def test_close_error_is_not_hidden_by_primary_error(self):
        dll, calls = self.fake_dll("SetVoltage")
        dll.chr62000_close.side_effect = RuntimeError("close failed")
        with self.assertRaises(RuntimeError) as caught:
            chroma.run_branch(dll, chroma.BRANCHES[0])
        self.assertIn("SetVoltage", str(caught.exception))
        self.assertIn("close failed", str(caught.exception))

    def test_warning_is_reported_but_does_not_skip_off(self):
        dll, calls = self.fake_dll()
        dll.chr62000_SetVoltage.side_effect = None
        dll.chr62000_SetVoltage.return_value = 5
        with self.assertRaises(RuntimeError) as caught:
            chroma.run_branch(dll, chroma.BRANCHES[0])
        self.assertIn("warning status 5", str(caught.exception))
        self.assertIn(("SetOutput", (123, 0)), calls)
        self.assertEqual(calls[-1][0], "close")

    def test_wrong_driver_hash_is_rejected_without_dll_load(self):
        with patch("builtins.open", unittest.mock.mock_open(read_data=b"synthetic-not-a-driver")):
            with self.assertRaises(ValueError):
                chroma.verify_driver(os.path.abspath("synthetic-chroma.dll"))

    def test_unverified_mapping_never_spawns_or_loads(self):
        with patch.object(chroma.subprocess, "Popen") as spawn:
            with self.assertRaises(RuntimeError):
                chroma.ChromaFocalStop()()
            spawn.assert_not_called()

    def test_constructing_verified_adapter_is_still_cold(self):
        with patch.object(chroma.subprocess, "Popen") as spawn, patch.object(chroma, "verify_driver") as verify:
            adapter = chroma.ChromaFocalStop(resources_verified=True)
        self.assertTrue(adapter.resources_verified)
        spawn.assert_not_called()
        verify.assert_not_called()

    def test_three_off_workers_launch_before_wait_and_one_failure_does_not_skip_others(self):
        adapter = chroma.ChromaFocalStop(resources_verified=True)
        processes, events = {}, []
        for number in (3, 2, 1):
            process = Mock()
            process.returncode = 7 if number == 2 else 0
            process.poll.return_value = process.returncode
            def communicate(focal):
                def wait(**_kwargs):
                    events.append(("wait", focal))
                    return (None, b"synthetic focal failure" if focal == 2 else b"")
                return wait
            process.communicate.side_effect = communicate(number)
            processes[number] = process
        def spawn(arguments, **kwargs):
            number = int(arguments[-1])
            events.append(("spawn", number))
            self.assertEqual(kwargs["creationflags"], 0x08000000)
            return processes[number]
        with patch.object(adapter, "ensure_ready"), patch.object(chroma.subprocess, "Popen", side_effect=spawn):
            with self.assertRaises(RuntimeError) as caught:
                adapter()
        self.assertEqual(events[:3], [("spawn", 3), ("spawn", 2), ("spawn", 1)])
        self.assertIn("F2: synthetic focal failure", str(caught.exception))
        for number, process in processes.items():
            self.assertIn(("wait", number), events)
            process.kill.assert_not_called()

    def test_timeout_kills_workers_and_reports_unknown_output(self):
        adapter = chroma.ChromaFocalStop(resources_verified=True)
        processes = []
        for _ in range(3):
            process = Mock()
            process.communicate.side_effect = [subprocess.TimeoutExpired("synthetic", 10), (None, b"")]
            process.poll.return_value = None
            processes.append(process)
        with patch.object(adapter, "ensure_ready"), patch.object(chroma.subprocess, "Popen", side_effect=processes):
            with self.assertRaises(RuntimeError) as caught:
                adapter()
        self.assertIn("output state unknown", str(caught.exception))
        for process in processes:
            process.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
