"""Cold process-supervision tests. All child processes are FakePopen objects."""
import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elyse_agent import acquisition_supervisor as module
from elyse_agent import acquisition_startup as startup


class FakeClock(object):
    def __init__(self):
        self.value = 0.0
        self.on_wait = None

    def now(self):
        return self.value

    def wait(self, seconds):
        self.value += seconds
        if self.on_wait is not None:
            self.on_wait()


class FakeGuard(object):
    def __init__(self):
        self.owned = False
        self.allowed = True
        self.acquires = self.releases = 0

    def acquire(self):
        self.acquires += 1
        if self.owned or not self.allowed:
            raise RuntimeError("another supervisor owns guard")
        self.owned = True
        return True

    def release(self):
        self.releases += 1
        self.owned = False


class FakeJournal(object):
    def __init__(self):
        self.record = None
        self.begins = []
        self.clears = []
        self.error = None

    def pending(self):
        if self.error == "pending":
            raise ValueError("unrelated/corrupt journal")
        return self.record is not None

    def begin(self, token, argv):
        if self.error == "begin" or self.record is not None:
            raise ValueError("journal creation refused")
        self.record = (token, tuple(argv))
        self.begins.append(self.record)

    def clear_confirmed_exit(self, token):
        if self.error == "clear" or not self.record or self.record[0] != token:
            raise ValueError("journal release refused")
        self.clears.append(token)
        self.record = None


class FakePopen(object):
    def __init__(self, number):
        self.pid = 900 + number
        self.returncode = None
        self.polls = self.waits = self.kills = 0
        self.poll_error = self.wait_error = False
        self.wrong_wait = False
        self.runtime_state = "IDLE"

    def poll(self):
        self.polls += 1
        if self.poll_error:
            raise RuntimeError("exit status unavailable")
        return self.returncode

    def wait(self, timeout):
        self.waits += 1
        if self.wait_error or self.returncode is None:
            raise RuntimeError("exit/join not confirmed")
        return self.returncode + 1 if self.wrong_wait else self.returncode

    def kill(self):
        self.kills += 1
        raise AssertionError("Supervisor must NEVER kill a live acquisition child")


class FakeFactory(object):
    def __init__(self, journal):
        self.journal = journal
        self.children, self.calls = [], []
        self.error = None

    def __call__(self, argv, **kwargs):
        if self.journal.record is None:
            raise AssertionError("Durable child intent must precede spawn")
        self.calls.append((argv, kwargs))
        if self.error:
            raise RuntimeError(self.error)
        child = FakePopen(len(self.children) + 1)
        self.children.append(child)
        return child


def make_supervisor(**kwargs):
    clock, guard, journal = FakeClock(), FakeGuard(), FakeJournal()
    factory, validator = FakeFactory(journal), Mock()
    supervisor = module.ColdAcquisitionSupervisor(
        os.path.abspath("pythonw.exe"), os.path.abspath("acquisition_server.pyw"),
        os.path.abspath("config.acquisition.json"), process_factory=factory,
        clock=clock.now, wait=clock.wait, guard=guard, journal=journal,
        path_validator=validator, **kwargs)
    return supervisor, clock, guard, journal, factory, validator


class SupervisorTests(unittest.TestCase):
    def test_import_construction_and_snapshot_are_cold(self):
        with patch.object(module.subprocess, "Popen") as spawn, \
                patch.object(module.os, "open") as opened, \
                patch.object(module, "_validate_files") as validate:
            importlib.reload(module)
            supervisor = module.ColdAcquisitionSupervisor(
                os.path.abspath("pythonw.exe"), os.path.abspath("acquisition_server.pyw"),
                os.path.abspath("config.acquisition.json"))
            state = supervisor.snapshot()
            self.assertEqual("COLD_NOT_STARTED", state["state"])
            self.assertFalse(state["auto_initialize"])
            self.assertFalse(state["command_replay"])
            self.assertFalse(state["runtime_recovery_marker_cleared"])
            json.dumps(state)
            spawn.assert_not_called()
            opened.assert_not_called()
            validate.assert_not_called()

    def test_fixed_cold_argv_and_no_shell_or_hardware_commands(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        state = supervisor.tick()
        argv, options = factory.calls[0]
        self.assertEqual(list(supervisor.argv), argv)
        self.assertEqual("--config", argv[2])
        self.assertEqual(4, len(argv))
        self.assertEqual(dict(cwd=os.path.dirname(supervisor.entrypoint), shell=False, close_fds=True), options)
        self.assertTrue(guard.owned)
        self.assertIsNotNone(journal.record)
        self.assertEqual("CHILD_RUNNING_HEALTH_UNKNOWN", state["state"])
        self.assertEqual("NOT_MEASURED", state["health_assessment"])
        self.assertEqual(1, state["launches"])
        self.assertEqual([], journal.clears)

    def test_confirmed_clean_stop_server_exit_never_restarts(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        child = factory.children[0]
        child.returncode = 0
        state = supervisor.tick()
        self.assertEqual("NORMAL_CHILD_EXIT_NO_RESTART", state["state"])
        self.assertTrue(state["terminal"])
        self.assertFalse(state["child_owned"])
        self.assertFalse(guard.owned)
        self.assertEqual(1, child.waits)
        self.assertEqual(0, child.kills)
        self.assertIsNone(journal.record)
        for _ in range(10):
            clock.value += 100
            supervisor.tick()
        self.assertEqual(1, len(factory.calls))

    def test_nonzero_crashes_backoff_exponentially_and_open_budget_circuit(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor(
            max_restarts=3, backoff_initial=1, backoff_max=2)
        supervisor.tick()
        for restart, delay in enumerate((1, 2, 2), 1):
            factory.children[-1].returncode = 7
            state = supervisor.tick()
            self.assertEqual("CRASH_BACKOFF_COLD_RESTART_ONLY", state["state"])
            self.assertEqual(restart, state["restarts_used"])
            self.assertAlmostEqual(clock.value + delay, state["next_restart_at"])
            before = len(factory.calls)
            for _ in range(20):
                supervisor.tick()
            self.assertEqual(before, len(factory.calls))
            clock.value += delay
            supervisor.tick()
            self.assertEqual(before + 1, len(factory.calls))
        factory.children[-1].returncode = -9
        state = supervisor.tick()
        self.assertEqual("CRASH_RESTART_CIRCUIT_OPEN", state["state"])
        self.assertTrue(state["terminal"])
        self.assertTrue(state["manual_intervention_required"])
        self.assertEqual(4, len(factory.calls))
        self.assertFalse(guard.owned)
        self.assertTrue(all(child.waits == 1 and child.kills == 0 for child in factory.children))

    def test_zero_restart_budget_still_allows_only_first_cold_launch(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor(max_restarts=0)
        supervisor.tick()
        factory.children[0].returncode = 1
        state = supervisor.tick()
        self.assertEqual("CRASH_RESTART_CIRCUIT_OPEN", state["state"])
        self.assertEqual(1, len(factory.calls))

    def test_live_child_is_never_killed_or_restarted_even_after_long_interval(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        for _ in range(10):
            clock.value += 3600
            supervisor.tick()
        self.assertEqual(1, len(factory.calls))
        self.assertEqual(0, factory.children[0].kills)
        self.assertTrue(guard.owned)
        self.assertIsNotNone(journal.record)

    def test_unresponsive_live_child_requires_manual_action_not_restart(self):
        health = Mock(return_value=False)
        supervisor, clock, guard, journal, factory, validator = make_supervisor(health_check=health)
        supervisor.tick()
        state = supervisor.tick()
        self.assertEqual("MANUAL_INTERVENTION_UNRESPONSIVE_CHILD", state["state"])
        self.assertTrue(state["child_owned"])
        self.assertTrue(guard.owned)
        self.assertFalse(state["physical_shutdown_acknowledged"])
        health.return_value = True
        for _ in range(3):
            clock.value += 100
            supervisor.tick()
        self.assertEqual(1, len(factory.calls))
        self.assertTrue(supervisor.snapshot()["manual_intervention_required"])
        factory.children[0].returncode = 2
        state = supervisor.tick()
        self.assertEqual("MANUAL_INTERVENTION_PRIOR_CHILD_EXITED", state["state"])
        self.assertEqual(0, factory.children[0].kills)

    def test_stop_request_keeps_live_child_guard_and_journal_until_confirmed_exit(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        supervisor.request_stop()
        state = supervisor.tick()
        self.assertEqual("STOP_REQUESTED_WAITING_FOR_CHILD_EXIT_NO_KILL", state["state"])
        self.assertFalse(state["terminal"])
        self.assertTrue(guard.owned)
        self.assertIsNotNone(journal.record)
        self.assertEqual(0, factory.children[0].kills)
        factory.children[0].returncode = 5
        state = supervisor.tick()
        self.assertEqual("STOPPED_AFTER_CHILD_EXIT", state["state"])
        self.assertFalse(guard.owned)
        self.assertEqual(1, len(factory.calls))

    def test_stop_during_backoff_prevents_next_launch(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        factory.children[0].returncode = 1
        supervisor.tick()
        supervisor.request_stop()
        state = supervisor.tick()
        self.assertEqual("STOPPED_WITHOUT_CHILD", state["state"])
        self.assertEqual(1, len(factory.calls))
        self.assertFalse(guard.owned)

    def test_stop_before_first_launch_never_acquires_guard_or_spawns(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.request_stop()
        state = supervisor.tick()
        self.assertEqual("STOPPED_BEFORE_LAUNCH", state["state"])
        self.assertEqual(0, guard.acquires)
        self.assertEqual([], factory.calls)

    def test_run_stop_waits_for_live_child_without_abandoning_it(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()

        def on_wait():
            if clock.value >= .3:
                factory.children[0].returncode = 0

        clock.on_wait = on_wait
        result = supervisor.run(stop_requested=lambda: clock.value >= .1)
        self.assertEqual("STOPPED_AFTER_CHILD_EXIT", result["state"])
        self.assertGreaterEqual(clock.value, .3)
        self.assertEqual(0, factory.children[0].kills)
        self.assertIsNone(journal.record)

    def test_bad_stop_hook_does_not_abandon_live_child(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()

        def stop():
            return "invalid" if factory.children else False

        def wait(seconds):
            clock.wait(seconds)
            if clock.value >= .2:
                factory.children[0].returncode = 0

        clock.on_wait = lambda: None
        with patch.object(module.time, "sleep", side_effect=wait):
            state = supervisor.run(stop_requested=stop)
        self.assertEqual("STOPPED_AFTER_CHILD_EXIT", state["state"])
        self.assertEqual(0, factory.children[0].kills)
        self.assertFalse(guard.owned)

    def test_poll_or_join_failure_never_releases_or_respawns_unconfirmed_child(self):
        for failure in ("poll_error", "wait_error", "wrong_wait"):
            supervisor, clock, guard, journal, factory, validator = make_supervisor()
            supervisor.tick()
            child = factory.children[0]
            child.returncode = 7
            setattr(child, failure, True)
            state = supervisor.tick()
            self.assertEqual("MANUAL_INTERVENTION_EXIT_OR_HEALTH_UNCONFIRMED", state["state"])
            self.assertTrue(state["child_owned"])
            self.assertTrue(guard.owned)
            self.assertIsNotNone(journal.record)
            self.assertEqual([], journal.clears)
            self.assertEqual(1, len(factory.calls))
            setattr(child, failure, False)
            supervisor.tick()
            self.assertEqual(1, len(factory.calls))
            self.assertFalse(guard.owned)

    def test_duplicate_supervisor_guard_fails_closed_before_journal_or_spawn(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        guard.allowed = False
        state = supervisor.tick()
        self.assertEqual("START_BLOCKED", state["state"])
        self.assertTrue(state["terminal"])
        self.assertEqual([], factory.calls)
        self.assertEqual([], journal.begins)

    def test_prior_child_journal_blocks_relaunch_without_pid_guessing(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        journal.record = ("0" * 32, ("previous-owner",))
        state = supervisor.tick()
        self.assertEqual("RECOVERY_REQUIRED_PRIOR_CHILD_UNCONFIRMED", state["state"])
        self.assertEqual([], factory.calls)
        self.assertEqual([], journal.clears)
        self.assertEqual(("0" * 32, ("previous-owner",)), journal.record)
        self.assertFalse(guard.owned)

    def test_supervisor_crash_orphan_journal_blocks_second_supervisor(self):
        first, clock, guard, journal, factory, validator = make_supervisor()
        first.tick()
        # Simulate OS releasing only the crashed supervisor's lock. The child
        # is still live; a PID value is deliberately not used as exit evidence.
        guard.owned = False
        second = module.ColdAcquisitionSupervisor(
            first.interpreter, first.entrypoint, first.config_path,
            process_factory=factory, clock=clock.now, wait=clock.wait,
            guard=guard, journal=journal, path_validator=validator)
        state = second.tick()
        self.assertEqual("RECOVERY_REQUIRED_PRIOR_CHILD_UNCONFIRMED", state["state"])
        self.assertEqual(1, len(factory.calls))
        self.assertIsNone(factory.children[0].returncode)
        self.assertEqual(0, factory.children[0].kills)

    def test_unknown_spawn_outcome_retains_journal_and_never_blindly_retries(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        factory.error = "Popen outcome unknown"
        state = supervisor.tick()
        self.assertEqual("RECOVERY_REQUIRED_SPAWN_OUTCOME_UNKNOWN", state["state"])
        self.assertIsNotNone(journal.record)
        for _ in range(10):
            clock.value += 100
            supervisor.tick()
        self.assertEqual(1, len(factory.calls))
        self.assertEqual([], journal.clears)

    def test_journal_errors_fail_closed_and_preserve_record(self):
        for failure in ("pending", "begin", "clear"):
            supervisor, clock, guard, journal, factory, validator = make_supervisor()
            if failure == "clear":
                supervisor.tick()
                factory.children[0].returncode = 0
            journal.error = failure
            state = supervisor.tick()
            self.assertTrue(state["terminal"])
            self.assertTrue(state["manual_intervention_required"])
            self.assertEqual([], journal.clears)
            if failure == "clear":
                self.assertIsNotNone(journal.record)
                self.assertEqual("RECOVERY_REQUIRED_CHILD_JOURNAL_RETAINED", state["state"])
            else:
                self.assertEqual([], factory.calls)

    def test_cold_restart_does_not_clear_runtime_recovery_required_state(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        factory.children[0].returncode = 8
        supervisor.tick()
        clock.value += 1
        supervisor.tick()
        factory.children[1].runtime_state = "RECOVERY_REQUIRED"
        for _ in range(3):
            supervisor.tick()
        self.assertEqual("RECOVERY_REQUIRED", factory.children[1].runtime_state)
        self.assertFalse(supervisor.snapshot()["runtime_recovery_marker_cleared"])
        self.assertEqual(2, len(factory.calls))

    def test_invalid_paths_or_unbounded_configuration_rejected_cold(self):
        paths = (os.path.abspath("pythonw.exe"), os.path.abspath("app.pyw"), os.path.abspath("cfg.json"))
        for kwargs in (dict(max_restarts=True), dict(max_restarts=-1), dict(max_restarts=21),
                       dict(backoff_initial=0), dict(backoff_max=301),
                       dict(poll_interval=0), dict(backoff_initial=float("nan"))):
            with self.assertRaises(ValueError):
                module.ColdAcquisitionSupervisor(*paths, **kwargs)
        with self.assertRaises(ValueError):
            module.ColdAcquisitionSupervisor("pythonw.exe", paths[1], paths[2])
        with self.assertRaises(ValueError):
            module.ColdAcquisitionSupervisor(os.path.abspath("cmd.exe"), paths[1], paths[2])


class FileBoundaryTests(unittest.TestCase):
    def test_config_scoped_standard_file_lock_excludes_duplicate_owner(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "owned.supervisor.lock")
            first, second = module.FileInstanceGuard(path), module.FileInstanceGuard(path)
            first.acquire()
            try:
                with self.assertRaises((OSError, RuntimeError, ValueError)):
                    second.acquire()
            finally:
                first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_unrelated_lock_or_journal_is_never_overwritten_or_deleted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "unrelated")
            with open(path, "w") as source:
                source.write("unrelated content")
            with self.assertRaises(ValueError):
                module.FileInstanceGuard(path).acquire()
            journal = module.FileChildJournal(path, ("controlled",))
            with self.assertRaises(ValueError):
                journal.pending()
            with self.assertRaises((OSError, ValueError)):
                journal.begin("0" * 32, ("controlled",))
            with self.assertRaises(ValueError):
                journal.clear_confirmed_exit("0" * 32)
            with open(path) as source:
                self.assertEqual("unrelated content", source.read())

    def test_child_journal_requires_matching_token_and_controlled_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "owned.supervisor-child.json")
            journal = module.FileChildJournal(path, ("pythonw.exe", "app.pyw", "--config", "cfg.json"))
            self.assertFalse(journal.pending())
            journal.begin("a" * 32, journal.argv)
            self.assertTrue(journal.pending())
            with self.assertRaises(ValueError):
                journal.clear_confirmed_exit("b" * 32)
            self.assertTrue(os.path.isfile(path))
            journal.clear_confirmed_exit("a" * 32)
            self.assertFalse(os.path.exists(path))

    def test_oversized_or_malformed_journal_is_rejected_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "owned.supervisor-child.json")
            journal = module.FileChildJournal(path, ("controlled",))
            payloads = [b"{" + b" " * module.MAX_JOURNAL_BYTES,
                        b"{malformed", b"\xff", b"[]"]
            for payload in payloads:
                with open(path, "wb") as target:
                    target.write(payload)
                for action in (journal.pending, lambda: journal.clear_confirmed_exit("a" * 32)):
                    with self.assertRaises(ValueError):
                        action()
                with open(path, "rb") as source:
                    self.assertEqual(payload, source.read())

    def test_generated_journal_is_bounded_before_exclusive_file_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "owned.supervisor-child.json")
            journal = module.FileChildJournal(path, ("controlled", "x" * module.MAX_JOURNAL_BYTES))
            with self.assertRaises(ValueError):
                journal.begin("a" * 32, journal.argv)
            self.assertFalse(os.path.exists(path))

    def test_journal_read_uses_exact_byte_bound_before_json_decode(self):
        journal = module.FileChildJournal(os.path.abspath("fake.supervisor-child.json"), ("controlled",))
        source = Mock()
        source.read.return_value = b"x" * (module.MAX_JOURNAL_BYTES + 1)
        opened = Mock()
        opened.__enter__ = Mock(return_value=source)
        opened.__exit__ = Mock(return_value=False)
        with patch("builtins.open", return_value=opened), patch.object(module.json, "loads") as decode:
            with self.assertRaises(ValueError):
                journal._read()
        source.read.assert_called_once_with(4097)
        decode.assert_not_called()

    def test_startup_writes_only_requested_temp_launcher_and_never_launches(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, name) for name in ("app.pyw", "cfg.json", "pythonw.exe")]
            for path in paths:
                with open(path, "w") as source:
                    source.write("")
            with patch.object(module.subprocess, "Popen") as spawn, \
                    patch.object(startup, "startup_directory", side_effect=AssertionError("real Startup forbidden")):
                target = startup.install_startup(paths[0], paths[1], folder, paths[2])
                spawn.assert_not_called()
                with open(target, encoding="utf-8") as source:
                    code = source.read()
                self.assertTrue(code.startswith(startup.MARKER))
                self.assertNotIn("initialize", code.lower())
                exec(compile(code, target, "exec"), {})
                args, kwargs = spawn.call_args
                self.assertTrue(args[0][1].endswith("acquisition_supervisor.py"))
                self.assertEqual(["--interpreter", paths[2], "--entrypoint", paths[0], "--config", paths[1]], args[0][2:])
                self.assertFalse(kwargs["shell"])
                self.assertTrue(kwargs["close_fds"])
                startup.install_startup(paths[0], paths[1], folder, paths[2])


class QualifiedRecoveryTests(unittest.TestCase):
    def prepared(self, folder):
        spawn = Mock(return_value=FakePopen(1))
        supervisor = module.ColdAcquisitionSupervisor(
            os.path.join(folder, "pythonw.exe"), os.path.join(folder, "app.pyw"),
            os.path.join(folder, "cfg.json"), process_factory=spawn,
            path_validator=Mock())
        journal = supervisor._journal
        journal.begin("a" * 32, supervisor.argv)
        return supervisor, journal, spawn

    def proof(self, record, digest, **overrides):
        values = dict(record_token=record["token"], controlled_argv=tuple(record["argv"]),
                      record_sha256=digest, verification_source="Synthetic qualified local checker; test only",
                      no_matching_gui_child=True, no_native_children=True, no_ni_competitors=True)
        values.update(overrides)
        return module.RecoveryQuiescenceProof(**values)

    def bytes_at(self, path):
        with open(path, "rb") as source:
            return source.read()

    def test_successful_qualified_recovery_stays_cold_and_preserves_ni_barrier(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            ni_marker = os.path.join(folder, "runtime-ni-recovery.marker")
            with open(ni_marker, "wb") as target:
                target.write(b"DIRTY OWNERSHIP MUST REMAIN")
            self.assertEqual("RECOVERY_REQUIRED_PRIOR_CHILD_UNCONFIRMED", supervisor.tick()["state"])
            result = supervisor.recover_prior_child(True, self.proof)
            self.assertTrue(result["recovered"])
            self.assertFalse(result["production_verifier_included"])
            self.assertFalse(result["unattended_deployment_qualified"])
            self.assertFalse(result["runtime_ni_recovery_marker_cleared"])
            self.assertFalse(result["physical_shutdown_acknowledged"])
            self.assertEqual(["no_matching_gui_child", "no_native_children", "no_ni_competitors"],
                             result["checked_categories"])
            self.assertFalse(os.path.exists(journal.path))
            self.assertEqual(b"DIRTY OWNERSHIP MUST REMAIN", self.bytes_at(ni_marker))
            self.assertEqual("COLD_NOT_STARTED", supervisor.snapshot()["state"])
            self.assertFalse(supervisor.snapshot()["child_owned"])
            self.assertFalse(supervisor.snapshot()["supervisor_guard_held"])
            spawn.assert_not_called()
            json.dumps(result)

    def test_off_confirmation_and_qualified_checker_default_to_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            original = self.bytes_at(journal.path)
            for off in (False, None, 1, "True"):
                with self.assertRaises(ValueError):
                    supervisor.recover_prior_child(off, self.proof)
            with self.assertRaises(RuntimeError):
                supervisor.recover_prior_child(True)
            self.assertFalse(os.path.exists(supervisor._guard.path))
            self.assertEqual(original, self.bytes_at(journal.path))
            spawn.assert_not_called()

    def test_direct_journal_recovery_requires_matching_held_config_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            original = self.bytes_at(journal.path)
            with self.assertRaises(RuntimeError):
                journal.recover_prior(True, self.proof)
            wrong_guard = module.FileInstanceGuard(os.path.join(folder, "other.supervisor.lock"))
            wrong_guard.acquire()
            try:
                with self.assertRaises(RuntimeError):
                    journal.recover_prior(True, self.proof, wrong_guard)
            finally:
                wrong_guard.release()
            self.assertEqual(original, self.bytes_at(journal.path))

    def test_current_child_or_current_owner_prevents_recovery(self):
        supervisor, clock, guard, journal, factory, validator = make_supervisor()
        supervisor.tick()
        checker = Mock()
        with self.assertRaises(RuntimeError):
            supervisor.recover_prior_child(True, checker)
        self.assertTrue(guard.owned)
        self.assertIsNotNone(journal.record)
        self.assertEqual(1, len(factory.calls))
        checker.assert_not_called()

    def test_live_config_guard_owner_prevents_recovery_before_checker(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            current_owner = module.FileInstanceGuard(supervisor._guard.path)
            original = self.bytes_at(journal.path)
            current_owner.acquire()
            checker = Mock()
            try:
                with self.assertRaises((OSError, RuntimeError, ValueError)):
                    supervisor.recover_prior_child(True, checker)
                self.assertTrue(current_owner.held)
            finally:
                current_owner.release()
            checker.assert_not_called()
            self.assertEqual(original, self.bytes_at(journal.path))

    def test_plain_json_boolean_or_partial_absence_claim_is_not_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            original = self.bytes_at(journal.path)
            for value in (True, {"no_matching_gui_child": True, "no_native_children": True,
                                  "no_ni_competitors": True}):
                with self.assertRaises(TypeError):
                    supervisor.recover_prior_child(True, lambda record, digest: value)
            for absent in ("no_matching_gui_child", "no_native_children", "no_ni_competitors"):
                def partial(record, digest):
                    return self.proof(record, digest, **{absent: False})
                with self.assertRaises(ValueError):
                    supervisor.recover_prior_child(True, partial)
            self.assertEqual(original, self.bytes_at(journal.path))
            spawn.assert_not_called()

    def test_evidence_must_bind_exact_token_argv_hash_and_not_pid_only(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            original = self.bytes_at(journal.path)
            changes = [dict(record_token="b" * 32), dict(record_sha256="0" * 64),
                       dict(controlled_argv=(supervisor.interpreter, "wrong.pyw", "--config", supervisor.config_path)),
                       dict(identity_method="PID_ONLY")]
            for replacement in changes:
                def mismatch(record, digest):
                    return self.proof(record, digest, **replacement)
                with self.assertRaises(ValueError):
                    supervisor.recover_prior_child(True, mismatch)
            self.assertEqual(original, self.bytes_at(journal.path))

    def test_changed_record_or_even_changed_whitespace_is_preserved(self):
        for change_token in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                supervisor, journal, spawn = self.prepared(folder)
                modified = []

                def checker(record, digest):
                    proof = self.proof(record, digest)
                    if change_token:
                        record["token"] = "b" * 32
                    payload = json.dumps(record, sort_keys=True).encode("utf-8") + b"\n"
                    with open(journal.path, "wb") as target:
                        target.write(payload)
                    modified.append(payload)
                    return proof

                with self.assertRaises(ValueError):
                    supervisor.recover_prior_child(True, checker)
                self.assertEqual(modified[0], self.bytes_at(journal.path))
                self.assertFalse(supervisor._guard.held)
                spawn.assert_not_called()

    def test_unrelated_or_changed_identity_record_is_preserved_before_checker(self):
        for unrelated in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                supervisor, journal, spawn = self.prepared(folder)
                if unrelated:
                    replacement = b"unrelated record"
                else:
                    record = journal._read()
                    record["argv"][1] = os.path.join(folder, "other.pyw")
                    replacement = json.dumps(record).encode("utf-8")
                with open(journal.path, "wb") as target:
                    target.write(replacement)
                checker = Mock()
                with self.assertRaises(ValueError):
                    supervisor.recover_prior_child(True, checker)
                checker.assert_not_called()
                self.assertEqual(replacement, self.bytes_at(journal.path))

    def test_checker_failure_or_guard_loss_preserves_prior_record(self):
        with tempfile.TemporaryDirectory() as folder:
            supervisor, journal, spawn = self.prepared(folder)
            original = self.bytes_at(journal.path)
            with self.assertRaises(RuntimeError):
                supervisor.recover_prior_child(True, Mock(side_effect=RuntimeError("absence unproven")))

            def lose_guard(record, digest):
                result = self.proof(record, digest)
                supervisor._guard.release()
                return result

            with self.assertRaises(RuntimeError):
                supervisor.recover_prior_child(True, lose_guard)
            self.assertEqual(original, self.bytes_at(journal.path))
            self.assertFalse(supervisor._guard.held)
            spawn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
