"""Fake-only native/process contracts; never creates a process or loads a DLL."""
import ctypes
import importlib
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elyse_agent import chroma_focal_command as command
from elyse_agent import chroma_focal_stop as source


class FakeClock(object):
    def __init__(self):
        self.value = 0.0
        self.events = []
        self.on_wait = None

    def now(self):
        return self.value

    def wait(self, seconds):
        self.events.append(("sleep", seconds))
        self.value += seconds
        if self.on_wait:
            self.on_wait()


class FakeProcess(object):
    def __init__(self, clock, focal, duration=.06, code=0, unkillable=False,
                 kill_error=False, join_error=False, poll_error=False,
                 diagnostics_error=False, stderr=b""):
        self.clock, self.focal = clock, focal
        self.end = clock.value + duration
        self.code = code
        self.returncode = None
        self.unkillable, self.kill_error = unkillable, kill_error
        self.join_error, self.poll_error = join_error, poll_error
        self.diagnostics_error = diagnostics_error
        self.stderr = stderr
        self.kills, self.joins, self.communications = 0, 0, 0
        self.pid = 100 + focal

    def poll(self):
        self.clock.events.append(("poll", self.focal))
        if self.poll_error:
            raise RuntimeError("poll failure")
        if self.returncode is None and self.clock.value >= self.end:
            self.returncode = self.code
        return self.returncode

    def kill(self):
        self.kills += 1
        self.clock.events.append(("kill", self.focal))
        if self.kill_error:
            raise RuntimeError("kill failure")
        if not self.unkillable:
            self.returncode = -9

    def wait(self, timeout):
        self.joins += 1
        self.clock.events.append(("join", self.focal, timeout))
        if self.join_error:
            raise RuntimeError("join failure")
        code = self.poll()
        if code is None:
            raise subprocess.TimeoutExpired("fake Chroma", timeout)
        return code

    def communicate(self, timeout):
        self.communications += 1
        self.clock.events.append(("communicate", self.focal, timeout))
        if self.diagnostics_error:
            raise RuntimeError("diagnostics failure")
        return (None, self.stderr)


class FakeFactory(object):
    def __init__(self, clock, options=None):
        self.clock, self.options = clock, options or {}
        self.processes = []
        self.calls = []
        self.fail_spawn = None
        self.on_spawn = None

    def __call__(self, arguments, **kwargs):
        focal, output = int(arguments[-2]), arguments[-1]
        self.clock.events.append(("spawn", focal, output))
        self.calls.append((arguments, kwargs))
        if len(self.calls) == self.fail_spawn:
            raise RuntimeError("spawn failure")
        process = FakeProcess(self.clock, focal, **self.options.get(focal, {}))
        self.processes.append(process)
        if self.on_spawn:
            self.on_spawn()
        return process


def make_adapter(options=None, timeout=1, resources_verified=True):
    clock = FakeClock()
    factory = FakeFactory(clock, options)
    verifier, platform = Mock(), Mock(return_value=True)
    adapter = command.ChromaFocalCommand(
        resources_verified=resources_verified, timeout=timeout,
        process_factory=factory, clock=clock.now, wait=clock.wait,
        driver_verifier=verifier, platform_check=platform)
    return adapter, clock, factory, verifier, platform


def fake_dll(statuses=None, empty_session=False):
    statuses = statuses or {}
    dll, calls = Mock(), []

    def bind(name):
        def invoke(*args):
            calls.append((name, args))
            if name == "init" and not empty_session:
                args[3]._obj.value = 321
            value = statuses.get(name, 0)
            if isinstance(value, Exception):
                raise value
            return value
        return invoke

    for name in ("init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close"):
        getattr(dll, "chr62000_" + name).side_effect = bind(name)
    return dll, calls


class NativeChainTests(unittest.TestCase):
    def test_all_three_source_on_and_off_six_call_chains(self):
        for output in (False, True):
            for branch in source.BRANCHES:
                dll, calls = fake_dll()
                source.run_branch(dll, branch, output_enabled=output)
                self.assertEqual(["init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close"],
                                 [item[0] for item in calls])
                self.assertEqual((branch[1].encode("ascii"), 0, 1), calls[0][1][:3])
                self.assertEqual(list(branch[2:]), [calls[i][1][1] for i in (1, 2, 3)])
                self.assertTrue(all(value > 0 for value in branch[2:]))
                self.assertEqual((321, int(output)), calls[4][1])
                self.assertEqual((321,), calls[5][1])
                self.assertEqual([ctypes.c_uint32, ctypes.c_uint16], dll.chr62000_SetOutput.argtypes)
                self.assertEqual(ctypes.c_int32, dll.chr62000_SetOutput.restype)

    def test_exact_boolean_preflight_never_touches_dll(self):
        for invalid in (0, 1, None, "1", [], object()):
            dll = Mock()
            with self.assertRaises(ValueError):
                source.run_branch(dll, source.BRANCHES[0], output_enabled=invalid)
            self.assertEqual([], dll.mock_calls)

    def test_each_native_failure_is_reported_and_session_close_attempted(self):
        names = ("init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close")
        for output in (False, True):
            for name in names:
                dll, calls = fake_dll({name: -7})
                with self.assertRaises(RuntimeError) as raised:
                    source.run_branch(dll, source.BRANCHES[0], output_enabled=output)
                self.assertIn(name, str(raised.exception))
                self.assertEqual("close", calls[-1][0])
                expected = list(names[:names.index(name) + 1])
                if name != "close":
                    expected.append("close")
                self.assertEqual(expected, [item[0] for item in calls])

    def test_every_native_warning_continues_output_and_close_but_fails(self):
        for output in (False, True):
            for name in ("init", "SetVoltage", "SetCurrentSlew", "SetCurrent", "SetOutput", "close"):
                dll, calls = fake_dll({name: 3})
                with self.assertRaises(RuntimeError) as raised:
                    source.run_branch(dll, source.BRANCHES[0], output_enabled=output)
                self.assertIn("warning status 3", str(raised.exception))
                self.assertIn(("SetOutput", (321, int(output))), calls)
                self.assertEqual("close", calls[-1][0])

    def test_native_primary_and_close_errors_both_retained(self):
        dll, calls = fake_dll({"SetCurrent": -1, "close": RuntimeError("close failed")})
        with self.assertRaises(RuntimeError) as raised:
            source.run_branch(dll, source.BRANCHES[0], output_enabled=True)
        self.assertIn("SetCurrent", str(raised.exception))
        self.assertIn("close failed", str(raised.exception))
        self.assertEqual("close", calls[-1][0])

    def test_empty_session_skips_setters_and_does_not_close_unknown_session(self):
        dll, calls = fake_dll(empty_session=True)
        with self.assertRaises(RuntimeError):
            source.run_branch(dll, source.BRANCHES[0], output_enabled=True)
        self.assertEqual(["init"], [item[0] for item in calls])

    def test_cli_exact_worker_output_flag_only(self):
        for invalid in ([], ["--worker", "driver", "1", "True"],
                        ["--worker", "driver", "4", "1"], ["--worker", "driver", "1"]):
            with patch.object(command, "verify_driver") as verifier:
                with self.assertRaises(ValueError):
                    command.worker(invalid)
                verifier.assert_not_called()
        for flag in ("0", "1"):
            with patch.object(command, "verify_driver") as verifier, \
                    patch.object(command, "_x86_windows", return_value=True), \
                    patch.object(command.ctypes, "WinDLL", create=True) as load, \
                    patch.object(command, "run_branch") as run:
                command.worker(["--worker", "driver", "2", flag])
                verifier.assert_called_once_with("driver")
                run.assert_called_once_with(load.return_value, source.BRANCHES[1], output_enabled=flag == "1")


class ProcessContractTests(unittest.TestCase):
    def test_import_and_construction_are_cold_even_if_mapping_verified(self):
        with patch.object(command.subprocess, "Popen") as spawn, \
                patch.object(source, "verify_driver") as verify, \
                patch.object(command.ctypes, "WinDLL", create=True) as load:
            importlib.reload(command)
            adapter = command.ChromaFocalCommand(resources_verified=True)
            adapter.ensure_quiescent()
            self.assertEqual(0, adapter.pending_worker_count)
            spawn.assert_not_called()
            verify.assert_not_called()
            load.assert_not_called()

    def test_unverified_or_wrong_arch_or_hash_never_spawns(self):
        adapter, clock, factory, verify, platform = make_adapter(resources_verified=False)
        with self.assertRaises(RuntimeError):
            adapter.execute(True, lambda: False)
        self.assertEqual([], factory.calls)
        verify.assert_not_called()
        platform.assert_not_called()
        adapter.resources_verified = True
        platform.return_value = False
        with self.assertRaises(RuntimeError):
            adapter.ensure_ready()
        verify.assert_not_called()
        platform.return_value = True
        verify.side_effect = ValueError("wrong hash")
        with self.assertRaises(ValueError):
            adapter.execute(False, lambda: False)
        self.assertEqual([], factory.calls)

    def test_invalid_configuration_or_state_preflight_has_no_io(self):
        for timeout in (False, 0, 31, float("inf"), float("nan"), "1"):
            with self.assertRaises(ValueError):
                command.ChromaFocalCommand(timeout=timeout)
        adapter, clock, factory, verify, platform = make_adapter()
        for output in (None, 0, 1, "False"):
            with self.assertRaises(ValueError):
                adapter.execute(output, lambda: False)
        with self.assertRaises(ValueError):
            adapter.execute(True, None)
        self.assertEqual([], factory.calls)
        verify.assert_not_called()

    def test_three_hidden_workers_are_parallel_and_all_joined_before_success(self):
        for enabled in (False, True):
            adapter, clock, factory, verify, platform = make_adapter()
            result = adapter.execute(enabled, lambda: False)
            self.assertEqual([("spawn", 3, str(int(enabled))), ("spawn", 2, str(int(enabled))),
                              ("spawn", 1, str(int(enabled)))], clock.events[:3])
            self.assertTrue(result["completed"])
            self.assertFalse(result["hardware_acknowledged"])
            self.assertEqual("UNKNOWN", result["physical_output_state"])
            self.assertEqual(0, adapter.pending_worker_count)
            for process in factory.processes:
                self.assertEqual(0, process.kills)
                self.assertEqual(1, process.joins)
                self.assertEqual(1, process.communications)
            for arguments, kwargs in factory.calls:
                self.assertIn("elyse_agent.chroma_focal_command", arguments)
                self.assertEqual(0x08000000, kwargs["creationflags"])
                self.assertEqual(subprocess.DEVNULL, kwargs["stdin"])
                self.assertEqual(subprocess.DEVNULL, kwargs["stdout"])
            json.dumps(adapter.snapshot())

    def test_cancellation_with_three_running_workers_kills_and_joins_all(self):
        adapter, clock, factory, verify, platform = make_adapter({n: {"duration": 100} for n in (3, 2, 1)})
        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(True, lambda: clock.value >= .04)
        self.assertIn("cancelled", str(raised.exception))
        self.assertEqual(3, len(factory.processes))
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertTrue(all(process.kills == 1 and process.joins == 1 for process in factory.processes))
        self.assertLessEqual(clock.value, .06)

    def test_cancel_before_spawn_or_part_way_through_spawn(self):
        adapter, clock, factory, verify, platform = make_adapter()
        with self.assertRaises(RuntimeError):
            adapter.execute(False, lambda: True)
        self.assertEqual([], factory.calls)
        with self.assertRaises(command.ChromaCommandError):
            adapter.execute(True, lambda: len(factory.processes) >= 2)
        self.assertEqual(2, len(factory.processes))
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertTrue(all(process.joins == 1 for process in factory.processes))

    def test_partial_spawn_failure_reaps_owned_workers(self):
        for failed in (1, 2, 3):
            adapter, clock, factory, verify, platform = make_adapter()
            factory.fail_spawn = failed
            with self.assertRaises(command.ChromaCommandError) as raised:
                adapter.execute(True, lambda: False)
            self.assertIn("spawn failure", str(raised.exception))
            self.assertEqual(failed, len(factory.calls))
            self.assertEqual(failed - 1, len(factory.processes))
            self.assertEqual(0, adapter.pending_worker_count)
            self.assertTrue(all(process.joins == 1 for process in factory.processes))

    def test_deadline_reaps_all_and_is_never_physical_off_confirmation(self):
        adapter, clock, factory, verify, platform = make_adapter({n: {"duration": 100} for n in (3, 2, 1)})
        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(False, lambda: False)
        self.assertIn("timeout", str(raised.exception))
        self.assertAlmostEqual(1, clock.value)
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertFalse(raised.exception.report["completed"])
        self.assertFalse(raised.exception.report["hardware_acknowledged"])
        self.assertTrue(all(process.joins == 1 for process in factory.processes))

    def test_failed_native_exit_reaps_siblings_and_retains_diagnostics(self):
        adapter, clock, factory, verify, platform = make_adapter({
            3: {"duration": .02, "code": 7, "stderr": b"warning status 3"},
            2: {"duration": 100}, 1: {"duration": 100}})
        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(True, lambda: False)
        self.assertIn("warning status 3", str(raised.exception))
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertTrue(all(process.joins == 1 for process in factory.processes))
        self.assertEqual(0, factory.processes[0].kills)
        self.assertEqual(1, factory.processes[1].kills)

    def test_off_failure_allows_independent_delayed_off_branches_to_complete(self):
        adapter, clock, factory, verify, platform = make_adapter({
            3: {"duration": .02, "code": 7, "stderr": b"first OFF branch failure"},
            2: {"duration": .08}, 1: {"duration": .12}})
        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(False, lambda: False)
        self.assertIn("first OFF branch failure", str(raised.exception))
        self.assertGreaterEqual(clock.value, .12)
        self.assertEqual([7, 0, 0], [process.returncode for process in factory.processes])
        self.assertTrue(all(process.kills == 0 for process in factory.processes))
        self.assertTrue(all(process.joins == 1 for process in factory.processes))
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertFalse(raised.exception.report["completed"])
        self.assertFalse(raised.exception.report["hardware_acknowledged"])
        self.assertTrue(all(arguments[-1] == "0" for arguments, kwargs in factory.calls))

    def test_each_cleanup_failure_is_reported_and_unconfirmed_handles_retained(self):
        for key in ("kill_error", "join_error", "poll_error", "diagnostics_error"):
            adapter, clock, factory, verify, platform = make_adapter({3: {key: True, "duration": 100}})
            with self.assertRaises(command.ChromaCommandError) as raised:
                adapter.execute(False, lambda: clock.value >= .02)
            self.assertTrue(raised.exception.report["cleanup_failures"])
            expected = 0 if key == "diagnostics_error" else 1
            self.assertEqual(expected, adapter.pending_worker_count)
            if expected:
                process = factory.processes[0]
                process.kill_error = process.join_error = process.poll_error = False
                adapter.ensure_quiescent()
                self.assertEqual(0, adapter.pending_worker_count)

    def test_primary_cancel_and_multiple_cleanup_failures_are_all_retained(self):
        adapter, clock, factory, verify, platform = make_adapter({
            3: {"duration": 100, "kill_error": True, "join_error": True},
            2: {"duration": 100, "join_error": True}})
        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(False, lambda: clock.value >= .02)
        error = str(raised.exception)
        for text in ("cancelled", "F3 worker kill", "F3 worker join", "F2 worker join",
                     "remain live or unconfirmed"):
            self.assertIn(text, error)
        self.assertEqual(2, adapter.pending_worker_count)
        self.assertFalse(raised.exception.report["completed"])
        self.assertFalse(raised.exception.report["hardware_acknowledged"])

    def test_ensure_quiescent_during_active_command_is_rejected(self):
        adapter, clock, factory, verify, platform = make_adapter()
        failures = []

        def while_spawning():
            for action in (adapter.ensure_quiescent, adapter.ensure_ready):
                try:
                    action()
                except RuntimeError as error:
                    failures.append(str(error))

        factory.on_spawn = while_spawning
        adapter.execute(True, lambda: False)
        self.assertEqual(6, len(failures))
        self.assertEqual(3, len(factory.calls))

    def test_unkillable_worker_blocks_all_commands_until_quiescence_confirmed(self):
        adapter, clock, factory, verify, platform = make_adapter({3: {"duration": 100, "unkillable": True}})
        with self.assertRaises(command.ChromaCommandError):
            adapter.execute(False, lambda: clock.value >= .02)
        self.assertEqual(1, adapter.pending_worker_count)
        spawned = len(factory.calls)
        verified = verify.call_count
        for output in (True, False):
            with self.assertRaises(command.ChromaCommandError):
                adapter.execute(output, lambda: False)
        with self.assertRaises(command.ChromaCommandError):
            adapter.ensure_ready()
        self.assertEqual(spawned, len(factory.calls))
        self.assertEqual(verified, verify.call_count)
        state = adapter.snapshot()
        self.assertEqual(1, state["pending_worker_count"])
        self.assertEqual(3, state["workers"][0]["focal"])
        self.assertEqual(103, state["workers"][0]["pid"])
        json.dumps(state)
        factory.processes[0].unkillable = False
        adapter.ensure_quiescent()
        self.assertEqual(0, adapter.pending_worker_count)
        factory.options = {}
        adapter.execute(True, lambda: False)
        self.assertEqual(spawned + 3, len(factory.calls))

    def test_join_return_without_confirmed_exit_remains_owned(self):
        adapter, clock, factory, verify, platform = make_adapter({3: {"duration": 100, "unkillable": True}})
        original = factory.__call__

        def spawn(arguments, **kwargs):
            process = original(arguments, **kwargs)
            if process.focal == 3:
                process.wait = lambda timeout: 0  # Untrusted/inconsistent join result.
            return process

        adapter._spawn = spawn
        with self.assertRaises(command.ChromaCommandError):
            adapter.execute(True, lambda: clock.value >= .02)
        self.assertEqual(1, adapter.pending_worker_count)

    def test_overlapping_on_off_is_rejected_without_second_worker_set(self):
        adapter, clock, factory, verify, platform = make_adapter()
        blocked = []

        def overlap():
            try:
                adapter.execute(False, lambda: False)
            except RuntimeError as error:
                blocked.append(str(error))

        factory.on_spawn = overlap
        adapter.execute(True, lambda: False)
        self.assertEqual(3, len(factory.calls))
        self.assertEqual(3, len(blocked))
        self.assertTrue(all("overlapping ON/OFF blocked" in error for error in blocked))

    def test_no_on_after_off_until_every_prior_worker_has_joined(self):
        adapter, clock, factory, verify, platform = make_adapter()
        adapter.execute(False, lambda: False)
        first = list(factory.processes)

        def on_spawn():
            self.assertTrue(all(process.joins >= 1 for process in first))
            self.assertTrue(all(process.returncode is not None for process in first))

        factory.on_spawn = on_spawn
        adapter.execute(True, lambda: False)
        self.assertEqual(6, len(factory.calls))

    def test_empty_quiescence_has_no_driver_or_process_or_clock_io(self):
        adapter, clock, factory, verify, platform = make_adapter()
        adapter.ensure_quiescent()
        adapter.ensure_quiescent()
        self.assertEqual([], clock.events)
        self.assertEqual([], factory.calls)
        verify.assert_not_called()
        platform.assert_not_called()

    def test_invalid_cancel_callback_after_spawns_still_reaps_all(self):
        adapter, clock, factory, verify, platform = make_adapter()

        def cancelled():
            return 1 if len(factory.calls) >= 3 else False

        with self.assertRaises(command.ChromaCommandError) as raised:
            adapter.execute(True, cancelled)
        self.assertIn("exact Boolean", str(raised.exception))
        self.assertEqual(0, adapter.pending_worker_count)
        self.assertTrue(all(process.joins == 1 for process in factory.processes))


if __name__ == "__main__":
    unittest.main()
