"""Cold-only GUI process supervision; Python 3.4, no import/construction I/O.

Only a confirmed nonzero child exit permits a capped, delayed restart. The
child receives exactly interpreter/entrypoint/--config: no Initialize, General,
command replay, NI, PSP, Tango, HTTP or physical OFF operation exists here.

A config-scoped standard-library file lock excludes concurrent supervisors.
A separate pre-spawn journal survives supervisor death: an existing journal
blocks startup, without guessing whether a recorded PID is dead or reusable.
This is NOT machine-wide NI ownership qualification. The acquisition runtime's
independent dirty-ownership/recovery barrier is never cleared by this module.
"""
import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
from .native_process_spawn import spawn_native_process
import sys
import threading
import time
import uuid


LOCK_MARKER = b"# ELYSE_ACQUISITION_SUPERVISOR_LOCK_V1\n"
CHILD_MARKER = "ELYSE_ACQUISITION_SUPERVISOR_CHILD_V1"
MAX_JOURNAL_BYTES = 4096
RECOVERY_IDENTITY_METHOD = "FULL_CONTROLLED_GUI_IDENTITY_AND_NATIVE_AND_NI_ABSENCE"


class RecoveryQuiescenceProof(object):
    """Trusted local-checker result, never a configuration/JSON permission flag.

    No production Windows absence verifier is supplied here. A commissioning-
    qualified checker must establish all three categories against the supplied
    full controlled identity, not merely a PID. Constructing this record does
    not itself perform those checks or qualify unattended deployment.
    """

    __slots__ = ("record_token", "controlled_argv", "record_sha256",
                 "verification_source", "identity_method", "no_matching_gui_child",
                 "no_native_children", "no_ni_competitors")

    def __init__(self, record_token, controlled_argv, record_sha256,
                 verification_source, no_matching_gui_child=False,
                 no_native_children=False, no_ni_competitors=False,
                 identity_method=RECOVERY_IDENTITY_METHOD):
        if (not isinstance(record_token, str) or len(record_token) != 32
                or any(character not in "0123456789abcdef" for character in record_token)
                or not isinstance(record_sha256, str) or len(record_sha256) != 64
                or any(character not in "0123456789abcdef" for character in record_sha256)
                or type(controlled_argv) is not tuple
                or len(controlled_argv) != 4 or controlled_argv[2] != "--config"
                or any(not isinstance(value, str) for value in controlled_argv)
                or not isinstance(verification_source, str)
                or not verification_source.strip() or len(verification_source) > 512
                or identity_method != RECOVERY_IDENTITY_METHOD
                or no_matching_gui_child is not True
                or no_native_children is not True or no_ni_competitors is not True):
            raise ValueError("Qualified full-identity GUI/native/NI absence evidence required")
        self.record_token = record_token
        self.controlled_argv = controlled_argv
        self.record_sha256 = record_sha256
        self.verification_source = verification_source
        self.identity_method = identity_method
        self.no_matching_gui_child = no_matching_gui_child
        self.no_native_children = no_native_children
        self.no_ni_competitors = no_ni_competitors


def _absolute(path, label):
    if not isinstance(path, str) or not path or not os.path.isabs(path) or "\x00" in path:
        raise ValueError("Absolute controlled " + label + " path required")
    return os.path.abspath(path)


class FileInstanceGuard(object):
    """Config-scoped OS file lock, not a PID-based or machine-wide NI lock."""

    def __init__(self, path):
        self.path = _absolute(path, "supervisor guard")
        self._stream = None

    @property
    def held(self):
        return self._stream is not None

    def acquire(self):
        if self._stream is not None:
            raise RuntimeError("Supervisor guard already acquired")
        stream = None
        try:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            except OSError:
                stream = open(self.path, "r+b")
                if stream.read(len(LOCK_MARKER)) != LOCK_MARKER:
                    raise ValueError("Refusing unrelated supervisor guard file")
            else:
                stream = os.fdopen(descriptor, "r+b")
                stream.write(LOCK_MARKER)
                stream.flush()
                os.fsync(stream.fileno())
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            elif sys.platform in ("linux", "darwin"):
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                raise RuntimeError("No qualified standard-library supervisor lock for this platform")
            self._stream = stream
            return True
        except Exception:
            if stream is not None:
                stream.close()
            raise

    def release(self):
        if self._stream is None:
            return
        stream, self._stream = self._stream, None
        try:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            elif sys.platform in ("linux", "darwin"):
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


class FileChildJournal(object):
    """One bounded process-ownership record, NOT telemetry or command history."""

    def __init__(self, path, argv):
        self.path = _absolute(path, "supervisor child journal")
        self.argv = tuple(argv)

    def _read_record_and_payload(self):
        with open(self.path, "rb") as source:
            payload = source.read(MAX_JOURNAL_BYTES + 1)
        if len(payload) > MAX_JOURNAL_BYTES:
            raise ValueError("Oversized supervisor child journal; manual recovery required")
        record = json.loads(payload.decode("utf-8", "strict"))
        if (not isinstance(record, dict) or record.get("marker") != CHILD_MARKER
                or type(record.get("schema_version")) is not int or record["schema_version"] != 1
                or not isinstance(record.get("token"), str)
                or len(record["token"]) != 32
                or any(character not in "0123456789abcdef" for character in record["token"])
                or not isinstance(record.get("argv"), list)
                or any(not isinstance(value, str) for value in record["argv"])
                or record.get("state") != "SPAWN_ATTEMPT_NOT_RELEASED"
                or record.get("auto_initialize") is not False
                or record.get("command_replay") is not False):
            raise ValueError("Unrelated or invalid supervisor child journal; manual recovery required")
        return record, payload

    def _read(self):
        return self._read_record_and_payload()[0]

    def pending(self):
        if not os.path.exists(self.path):
            return False
        self._read()  # Validate ownership marker; never execute recorded data.
        return True

    def begin(self, token, argv):
        if (tuple(argv) != self.argv or not isinstance(token, str) or len(token) != 32
                or any(character not in "0123456789abcdef" for character in token)):
            raise ValueError("Controlled supervisor child identity required")
        record = dict(marker=CHILD_MARKER, schema_version=1, token=token,
                      argv=list(argv), state="SPAWN_ATTEMPT_NOT_RELEASED",
                      auto_initialize=False, command_replay=False)
        payload = json.dumps(record, sort_keys=True).encode("utf-8")
        if len(payload) > MAX_JOURNAL_BYTES:
            raise ValueError("Controlled child identity exceeds bounded journal size")
        # Exclusivity before Popen closes the orphan/duplicate gap. Even a
        # failed spawn leaves the record: no child handle means no exit proof.
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())

    def clear_confirmed_exit(self, token):
        record = self._read()
        if record["token"] != token or tuple(record["argv"]) != self.argv:
            raise ValueError("Refusing to release another supervisor's child journal")
        os.remove(self.path)

    def recover_prior(self, electrical_off_confirmed=False, quiescence_checker=None, guard=None):
        """Deliberate local recovery only; never invoked by start/tick/main.

        The qualified injected checker receives (record_copy, raw_record_sha256)
        and returns RecoveryQuiescenceProof. No guessed Windows verifier exists.
        Exact operator OFF confirmation is necessary but is NOT absence proof.
        A held matching config guard plus unchanged bytes prevent a cooperating
        supervisor from replacing the record during the qualified check.
        Runtime NI dirty-ownership markers are outside this method's scope.
        """
        if electrical_off_confirmed is not True:
            raise ValueError("Exact local electrical-OFF confirmation required")
        if not callable(quiescence_checker):
            raise RuntimeError("Qualified local quiescence checker unavailable; recovery blocked")
        if len(self.argv) != 4 or self.argv[2] != "--config":
            raise ValueError("Full controlled GUI identity required for prior-child recovery")
        config_path = _absolute(self.argv[3], "recovery configuration")
        expected_guard = os.path.normcase(config_path + ".supervisor.lock")
        expected_journal = os.path.normcase(config_path + ".supervisor-child.json")
        if (os.path.normcase(self.path) != expected_journal
                or not isinstance(guard, FileInstanceGuard) or not guard.held
                or os.path.normcase(guard.path) != expected_guard):
            raise RuntimeError("Matching held config-scoped supervisor guard required")
        record, payload = self._read_record_and_payload()
        if tuple(record["argv"]) != self.argv:
            raise ValueError("Prior child identity differs; journal retained")
        digest = hashlib.sha256(payload).hexdigest()
        proof = quiescence_checker(copy.deepcopy(record), digest)
        if type(proof) is not RecoveryQuiescenceProof:
            raise TypeError("Typed qualified-checker evidence required; JSON/Boolean flags are not proof")
        if (proof.record_token != record["token"] or proof.controlled_argv != self.argv
                or proof.record_sha256 != digest
                or proof.identity_method != RECOVERY_IDENTITY_METHOD
                or proof.no_matching_gui_child is not True
                or proof.no_native_children is not True or proof.no_ni_competitors is not True):
            raise ValueError("Quiescence evidence does not bind the exact prior child record")
        if not guard.held:
            raise RuntimeError("Supervisor guard lost during recovery; journal retained")
        current_record, current_payload = self._read_record_and_payload()
        if current_payload != payload or current_record != record:
            raise ValueError("Prior child journal changed during verification; nothing removed")
        if not guard.held:
            raise RuntimeError("Supervisor guard lost before recovery release; journal retained")
        os.remove(self.path)
        return dict(scope="SUPERVISOR_CHILD_RECORD_ONLY", recovered=True,
                    record_sha256=digest, verification_source=proof.verification_source,
                    identity_method=proof.identity_method,
                    checked_categories=["no_matching_gui_child", "no_native_children", "no_ni_competitors"],
                    runtime_ni_recovery_marker_cleared=False,
                    production_verifier_included=False, unattended_deployment_qualified=False,
                    auto_initialize=False, command_replay=False,
                    physical_shutdown_acknowledged=False)


def _validate_files(paths):
    if not all(os.path.isfile(path) for path in paths):
        raise ValueError("Installed interpreter, GUI entrypoint and config must exist")


class ColdAcquisitionSupervisor(object):
    """A single cold child, capped crash retries, retained live ownership.

    tick() is deterministic with fake process/clock/guard/journal dependencies.
    request_stop() disables restarts, but NEVER kills or abandons a live child.
    run() continues monitoring that child until its exit is confirmed. Without
    health_check only process liveness is known; no healthy/hung claim is made.
    """

    def __init__(self, interpreter, entrypoint, config_path, process_factory=None,
                 clock=None, wait=None, guard=None, journal=None, health_check=None,
                 max_restarts=3, backoff_initial=1, backoff_max=30,
                 poll_interval=.1, path_validator=None):
        self.interpreter = _absolute(interpreter, "Python interpreter")
        self.entrypoint = _absolute(entrypoint, "GUI entrypoint")
        self.config_path = _absolute(config_path, "configuration")
        if os.path.basename(self.interpreter).lower() not in ("python.exe", "pythonw.exe"):
            raise ValueError("Controlled Python/pythonw executable required")
        if (type(max_restarts) is not int or not 0 <= max_restarts <= 20
                or any(type(value) not in (int, float) or not math.isfinite(value)
                       for value in (backoff_initial, backoff_max, poll_interval))
                or not .1 <= backoff_initial <= backoff_max <= 300
                or not .01 <= poll_interval <= 1):
            raise ValueError("Bounded restart budget, backoff and polling interval required")
        for hook in (process_factory, clock, wait, health_check, path_validator):
            if hook is not None and not callable(hook):
                raise TypeError("Supervisor hooks must be callable")
        self.argv = (self.interpreter, self.entrypoint, "--config", self.config_path)
        self._spawn = process_factory or spawn_native_process
        self._clock = clock or time.monotonic
        self._wait = wait or time.sleep
        self._validate_paths = path_validator or _validate_files
        self._guard = guard if guard is not None else FileInstanceGuard(self.config_path + ".supervisor.lock")
        self._journal = journal if journal is not None else FileChildJournal(
            self.config_path + ".supervisor-child.json", self.argv)
        for obj, names in ((self._guard, ("acquire", "release")),
                           (self._journal, ("pending", "begin", "clear_confirmed_exit"))):
            if any(not callable(getattr(obj, name, None)) for name in names):
                raise TypeError("Explicit supervisor guard/journal contract required")
        self._health = health_check
        self.max_restarts = max_restarts
        self.backoff_initial, self.backoff_max = backoff_initial, backoff_max
        self.poll_interval = poll_interval
        self._guard_held = self._started = self._terminal = self._stopping = False
        self._manual = False
        self._child = self._token = None
        self._next_restart = None
        self._restarts = self._launches = 0
        self._state, self._error, self._last_exit = "COLD_NOT_STARTED", None, None
        self._tick_lock = threading.Lock()
        self._last_prior_child_recovery = None

    def snapshot(self):
        pid = getattr(self._child, "pid", None) if self._child is not None else None
        return dict(state=self._state, error=self._error, terminal=self._terminal,
                    child_owned=self._child is not None,
                    child_pid=pid if type(pid) is int else None,
                    supervisor_guard_held=self._guard_held,
                    stop_requested=self._stopping, manual_intervention_required=self._manual,
                    launches=self._launches, restarts_used=self._restarts,
                    max_restarts=self.max_restarts, next_restart_at=self._next_restart,
                    last_confirmed_exit_code=self._last_exit,
                    health_assessment="NOT_MEASURED" if self._health is None else "INJECTED_PROBE_ONLY",
                    auto_initialize=False, command_replay=False,
                    runtime_recovery_marker_cleared=False,
                    prior_child_recovery=copy.deepcopy(self._last_prior_child_recovery),
                    physical_shutdown_acknowledged=False,
                    scope="CONFIG_SCOPED_PROCESS_OWNERSHIP_NOT_MACHINE_WIDE_NI_EXCLUSIVITY")

    def _now(self):
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Finite monotonic supervisor clock required")
        return value

    def _release_guard(self):
        if self._guard_held:
            try:
                self._guard.release()
            finally:
                self._guard_held = False

    def _manual_failure(self, state, error, terminal=False):
        self._manual, self._state, self._error = True, state, str(error)
        self._terminal = terminal
        if terminal and self._child is None:
            self._release_guard()

    def request_stop(self):
        self._stopping = True

    def recover_prior_child(self, electrical_off_confirmed=False, quiescence_checker=None):
        """Explicit local qualified recovery; success remains cold/no child.

        This has no CLI/HTTP/Tango route and is never called automatically.
        A live/current child, held current ownership or stop request refuses it.
        No production quiescence checker is installed by this module.
        """
        if electrical_off_confirmed is not True:
            raise ValueError("Exact local electrical-OFF confirmation required")
        if not callable(quiescence_checker):
            raise RuntimeError("Qualified local quiescence checker unavailable; recovery blocked")
        if not self._tick_lock.acquire(False):
            raise RuntimeError("Supervisor operation already executing")
        try:
            if self._child is not None or self._guard_held or self._stopping:
                raise RuntimeError("Prior-child recovery requires cold/no current child ownership")
            recover = getattr(self._journal, "recover_prior", None)
            if not callable(recover):
                raise RuntimeError("Qualified file-journal recovery contract unavailable")
            if self._guard.acquire() is not True:
                raise RuntimeError("Exclusive config supervisor guard not acquired")
            self._guard_held = True
            try:
                result = recover(electrical_off_confirmed=True,
                                 quiescence_checker=quiescence_checker, guard=self._guard)
            finally:
                self._release_guard()
            self._last_prior_child_recovery = copy.deepcopy(result)
            self._started = self._terminal = self._manual = False
            self._state, self._error = "COLD_NOT_STARTED", None
            self._next_restart = self._token = None
            return copy.deepcopy(result)
        finally:
            self._tick_lock.release()

    def _launch_cold(self):
        self._now()  # Validate clock before journal creation or process access.
        token = uuid.uuid4().hex
        self._journal.begin(token, self.argv)
        self._token = token
        try:
            child = self._spawn(list(self.argv), cwd=os.path.dirname(self.entrypoint),
                                shell=False, close_fds=True)
        except Exception as error:
            self._manual_failure("RECOVERY_REQUIRED_SPAWN_OUTCOME_UNKNOWN", error, terminal=True)
            return
        self._child = child
        if (child is None or not callable(getattr(child, "poll", None))
                or not callable(getattr(child, "wait", None))):
            # No usable process handle means no exit proof. Keep the journal;
            # never guess from a PID or blindly retry the spawn.
            self._child = None
            self._manual_failure("RECOVERY_REQUIRED_INVALID_CHILD_HANDLE",
                                 "Child spawn returned no usable poll/wait handle", terminal=True)
            return
        self._launches += 1
        self._next_restart = None
        self._state, self._error = "CHILD_RUNNING_HEALTH_UNKNOWN", None

    def _start(self):
        self._started = True
        try:
            self._validate_paths((self.interpreter, self.entrypoint, self.config_path))
            if self._guard.acquire() is not True:
                raise RuntimeError("Exclusive supervisor guard not acquired")
            self._guard_held = True
            if self._journal.pending():
                self._manual_failure("RECOVERY_REQUIRED_PRIOR_CHILD_UNCONFIRMED",
                                     "Existing child journal retained; no PID-based recovery or relaunch",
                                     terminal=True)
                return
            self._launch_cold()
        except Exception as error:
            self._manual_failure("START_BLOCKED", error, terminal=True)

    def tick(self):
        if not self._tick_lock.acquire(False):
            raise RuntimeError("Supervisor tick already executing")
        try:
            return self._tick_locked()
        finally:
            self._tick_lock.release()

    def _tick_locked(self):
        if self._terminal:
            return self.snapshot()
        if self._stopping and not self._started:
            self._terminal, self._state = True, "STOPPED_BEFORE_LAUNCH"
            return self.snapshot()
        if not self._started:
            self._start()
            return self.snapshot()
        if self._child is None:
            if self._stopping:
                self._terminal, self._state = True, "STOPPED_WITHOUT_CHILD"
                self._next_restart = None
                self._release_guard()
            elif self._next_restart is not None and self._now() >= self._next_restart:
                try:
                    self._launch_cold()
                except Exception as error:
                    self._manual_failure("RECOVERY_REQUIRED_RESTART_BLOCKED", error, terminal=True)
            return self.snapshot()
        try:
            code = self._child.poll()
            if code is None:
                if self._stopping:
                    self._state = "STOP_REQUESTED_WAITING_FOR_CHILD_EXIT_NO_KILL"
                elif self._health is not None:
                    healthy = self._health(self._child)
                    if type(healthy) is not bool:
                        raise ValueError("Health probe requires exact Boolean; no inferred healthy state")
                    if not healthy:
                        self._manual_failure("MANUAL_INTERVENTION_UNRESPONSIVE_CHILD",
                                             "Child is live but probe failed; automatic kill/restart forbidden")
                    elif not self._manual:
                        self._state = "CHILD_LIVE_PROBE_RESPONSIVE"
                return self.snapshot()
            if type(code) is not int:
                raise ValueError("Exact child exit code required")
            # poll alone is insufficient: reap and reconfirm the same child.
            if self._child.wait(timeout=0) != code or self._child.poll() != code:
                raise RuntimeError("Child exit/join not confirmed")
        except Exception as error:
            self._manual_failure("MANUAL_INTERVENTION_EXIT_OR_HEALTH_UNCONFIRMED", error)
            return self.snapshot()
        self._last_exit = code
        self._child = None  # Only after confirmed wait; no live handle discarded.
        try:
            self._journal.clear_confirmed_exit(self._token)
            self._token = None
        except Exception as error:
            self._manual_failure("RECOVERY_REQUIRED_CHILD_JOURNAL_RETAINED", error, terminal=True)
            return self.snapshot()
        if self._stopping or code == 0 or self._manual:
            self._terminal = True
            self._state = ("STOPPED_AFTER_CHILD_EXIT" if self._stopping else
                           "NORMAL_CHILD_EXIT_NO_RESTART" if code == 0 else
                           "MANUAL_INTERVENTION_PRIOR_CHILD_EXITED")
            self._release_guard()
        elif self._restarts >= self.max_restarts:
            self._manual_failure("CRASH_RESTART_CIRCUIT_OPEN",
                                 "Restart budget exhausted; no further cold launch", terminal=True)
        else:
            delay = min(self.backoff_max, self.backoff_initial * (2 ** self._restarts))
            self._restarts += 1
            try:
                self._next_restart = self._now() + delay
                self._state = "CRASH_BACKOFF_COLD_RESTART_ONLY"
            except Exception as error:
                self._manual_failure("MANUAL_INTERVENTION_RESTART_CLOCK", error, terminal=True)
        return self.snapshot()

    def run(self, stop_requested=None):
        if stop_requested is not None and not callable(stop_requested):
            raise TypeError("Optional stop_requested callback required")
        while True:
            try:
                if not self._stopping and stop_requested is not None:
                    stop = stop_requested()
                    if type(stop) is not bool:
                        raise ValueError("Stop callback requires exact Boolean")
                    if stop:
                        self.request_stop()
                result = self.tick()
                if result["terminal"] and not result["child_owned"]:
                    return result
                self._wait(self.poll_interval)
            except KeyboardInterrupt:
                # Ctrl-C is not permission to kill a possibly card-owning GUI.
                self.request_stop()
            except Exception as error:
                # A bad external probe/stop/wait hook must not make run() drop a
                # live child. Inhibit restarts, retain guard/journal, and keep
                # monitoring for confirmed exit with the standard bounded wait.
                self._manual_failure("MANUAL_INTERVENTION_SUPERVISOR_ERROR", error,
                                     terminal=self._child is None)
                self.request_stop()
                if self._child is None:
                    return self.snapshot()
                stop_requested = None
                self._wait = time.sleep


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interpreter", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    supervisor = ColdAcquisitionSupervisor(args.interpreter, args.entrypoint, args.config)
    result = supervisor.run()
    return 0 if result["state"] in ("NORMAL_CHILD_EXIT_NO_RESTART", "STOPPED_AFTER_CHILD_EXIT",
                                    "STOPPED_BEFORE_LAUNCH", "STOPPED_WITHOUT_CHILD") else 1


if __name__ == "__main__":
    sys.exit(main())
