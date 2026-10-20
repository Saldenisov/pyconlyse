"""Bounded source Chroma ON/OFF helper; Python 3.4, cold import/construction.

Both native paths initialize(reset=True), set the saved NONZERO voltage/slew/
current, set output 0 or 1, then close. OFF is not a zero-setpoint operation.
COM10/11/12 are saved defaults, not a qualified current Moxa configuration.

Three native workers run in parallel. No later command can overlap unfinished
workers: failed kill/join leaves owned handles here, and ensure_quiescent must
confirm their exit before any new spawn. Killing a worker is NOT physical OFF.
Timeout bounds native execution (1..30 seconds); safety reaping may additionally
wait 250 ms per owned worker. No network, driver load, or process access occurs
until explicit readiness/execution calls with commissioned configuration.
"""
import copy
import ctypes
import math
import os
import subprocess
import sys
import threading
import time

from .chroma_focal_stop import BRANCHES, DEFAULT_DLL, DRIVER_SHA256, run_branch, verify_driver


class ChromaCommandError(RuntimeError):
    """Failure retains diagnostics and whether process ownership is unresolved."""

    def __init__(self, failures, report):
        RuntimeError.__init__(self, "; ".join(failures))
        self.failures = tuple(failures)
        self.report = copy.deepcopy(report)


def _x86_windows():
    return sys.platform == "win32" and ctypes.sizeof(ctypes.c_void_p) == 4


class ChromaFocalCommand(object):
    def __init__(self, dll_path=DEFAULT_DLL, resources_verified=False, timeout=10,
                 process_factory=None, clock=None, wait=None, driver_verifier=None,
                 platform_check=None):
        if (type(resources_verified) is not bool or type(timeout) not in (int, float)
                or not math.isfinite(timeout) or not 1 <= timeout <= 30):
            raise ValueError("Invalid Chroma command configuration")
        if not isinstance(dll_path, str) or not dll_path:
            raise ValueError("Explicit Chroma DLL path required")
        for hook in (process_factory, clock, wait, driver_verifier, platform_check):
            if hook is not None and not callable(hook):
                raise TypeError("Chroma test hooks must be callable")
        self.dll_path = dll_path
        self.resources_verified = resources_verified
        self.timeout = float(timeout)
        self._spawn = process_factory or subprocess.Popen
        self._clock = clock or time.monotonic
        self._wait = wait or time.sleep
        self._verify = driver_verifier or verify_driver
        self._platform_check = platform_check or _x86_windows
        self._workers = []
        self._lock = threading.Lock()
        self.last_result = None

    @property
    def pending_worker_count(self):
        return len(self._workers)

    def snapshot(self):
        """JSON-safe bounded ownership diagnostics; never polls a process."""
        workers = []
        for record in self._workers:
            pid = getattr(record["process"], "pid", None)
            workers.append(dict(focal=record["focal"],
                                pid=pid if type(pid) is int else None,
                                state="OWNED_EXIT_NOT_CONFIRMED"))
        return dict(pending_worker_count=len(workers), workers=workers,
                    last_result=copy.deepcopy(self.last_result),
                    reviewed_driver_sha256=DRIVER_SHA256,
                    hardware_acknowledged=False, physical_output_state="UNKNOWN")

    def _now(self):
        value = self._clock()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Finite monotonic clock required")
        return value

    def _report(self, output_enabled=None):
        return dict(output_enabled=output_enabled, completed=False,
                    hardware_acknowledged=False, physical_output_state="UNKNOWN",
                    pending_workers=self.pending_worker_count,
                    branches=[], failures=[], cleanup_failures=[])

    def _raise(self, failures, report):
        report["failures"] = list(failures)
        report["pending_workers"] = self.pending_worker_count
        self.last_result = copy.deepcopy(report)
        raise ChromaCommandError(failures, report)

    def _cleanup_workers(self, report, check_exit=True):
        failures, retained = [], []
        for record in self._workers:
            focal, process = record["focal"], record["process"]
            joined, code = False, None
            try:
                code = process.poll()
            except Exception as error:
                failures.append("F{0} cleanup poll: {1}".format(focal, error))
            if code is None:
                try:
                    process.kill()
                except Exception as error:
                    failures.append("F{0} worker kill: {1}".format(focal, error))
            try:
                waited = process.wait(timeout=.25)
                code = process.poll()
                if waited is None or code is None:
                    raise RuntimeError("worker exit/join not confirmed")
                joined = True
            except Exception as error:
                failures.append("F{0} worker join: {1}".format(focal, error))
            if not joined:
                retained.append(record)
                report["branches"].append(dict(focal=focal, returncode=code,
                                                joined=False, stderr=""))
                continue
            record["returncode"] = code
            stderr = b""
            try:
                _stdout, stderr = process.communicate(timeout=.01)
            except Exception as error:
                failures.append("F{0} worker diagnostics: {1}".format(focal, error))
            if not isinstance(stderr, bytes):
                stderr = str(stderr or "").encode("utf-8", "replace")
            record["stderr"] = stderr.decode("utf-8", "replace")[:1000]
            report["branches"].append(dict(focal=focal, returncode=code,
                                            joined=True, stderr=record["stderr"]))
            if code != 0 and check_exit:
                failures.append("F{0} worker exit {1}: {2}".format(
                    focal, code, record["stderr"] or "native output state unknown"))
        self._workers = retained
        report["pending_workers"] = self.pending_worker_count
        report["cleanup_failures"].extend(failures)
        return failures

    def _quiescent_locked(self):
        if not self._workers:
            return
        report = self._report()
        # Quiescence is ownership recovery, not success of the old command.
        # A reaped nonzero exit does not itself prevent future commands.
        failures = self._cleanup_workers(report, check_exit=False)
        if self._workers:
            failures.append("Chroma workers remain live or unconfirmed; new commands blocked")
        if failures:
            self._raise(failures, report)

    def ensure_quiescent(self):
        """Retry retained worker cleanup; empty ownership performs no I/O."""
        if not self._lock.acquire(False):
            raise RuntimeError("Chroma command is executing; quiescence unavailable")
        try:
            self._quiescent_locked()
        finally:
            self._lock.release()

    def _ready_locked(self):
        self._quiescent_locked()
        if (type(self.timeout) not in (int, float) or not math.isfinite(self.timeout)
                or not 1 <= self.timeout <= 30):
            raise ValueError("Chroma execution timeout must remain within 1..30 seconds")
        if self.resources_verified is not True:
            raise RuntimeError("Focales command blocked: verify F3=COM10, F2=COM11, F1=COM12 on XP first")
        if self._platform_check() is not True:
            raise RuntimeError("Chroma requires the existing 32-bit XP Python process")
        self._verify(self.dll_path)

    def ensure_ready(self):
        if not self._lock.acquire(False):
            raise RuntimeError("Chroma command already executing")
        try:
            self._ready_locked()
        finally:
            self._lock.release()

    def execute(self, output_enabled, cancelled):
        """Execute one source ON/OFF helper behind external commissioning gates.

        Exceptions/cancellation still reap every owned worker. Unconfirmed exit
        is a retained-ownership failure, never a successful/physical OFF result.
        The cancel callback must return an exact Boolean; no guessed protocol.
        """
        if type(output_enabled) is not bool or not callable(cancelled):
            raise ValueError("Exact Boolean output state and cancellation callback required")
        if not self._lock.acquire(False):
            raise RuntimeError("Chroma command already executing; overlapping ON/OFF blocked")
        report, failures = self._report(output_enabled), []
        try:
            self._ready_locked()

            def check_cancel():
                value = cancelled()
                if type(value) is not bool:
                    raise ValueError("Cancellation callback must return an exact Boolean")
                if value:
                    raise RuntimeError("Chroma command cancelled; physical output state unknown")

            check_cancel()
            deadline = self._now() + self.timeout
            python = sys.executable
            if os.path.basename(python).lower() == "pythonw.exe":
                python = os.path.join(os.path.dirname(python), "python.exe")
            try:
                for branch in BRANCHES:
                    check_cancel()
                    if self._now() >= deadline:
                        raise RuntimeError("Chroma worker timeout; physical output state unknown")
                    process = self._spawn(
                        [python, "-m", "elyse_agent.chroma_focal_command", "--worker",
                         self.dll_path, str(branch[0]), "1" if output_enabled else "0"],
                        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE, creationflags=0x08000000)
                    self._workers.append(dict(focal=branch[0], process=process))
                while True:
                    check_cancel()
                    all_finished = True
                    for record in self._workers:
                        check_cancel()
                        code = record["process"].poll()
                        if code is None:
                            all_finished = False
                        elif code != 0 and output_enabled:
                            # ON is an explicit conservative fail-start policy.
                            # OFF branches are independent source chains: one
                            # failure must not kill siblings before their own
                            # Output(0)/Close can complete. Final cleanup still
                            # retains every OFF error; deadline/cancel stay live.
                            raise RuntimeError("F{0} native worker failed; physical output state unknown".format(
                                record["focal"]))
                    if all_finished:
                        break
                    remaining = deadline - self._now()
                    if remaining <= 0:
                        raise RuntimeError("Chroma worker timeout; physical output state unknown")
                    self._wait(min(.02, remaining))
            except Exception as error:
                failures.append(type(error).__name__ + ": " + str(error))
            finally:
                failures.extend(self._cleanup_workers(report))
            if self._workers:
                failures.append("Chroma workers remain live or unconfirmed; new commands blocked")
            if failures:
                self._raise(failures, report)
            report["completed"] = True
            report["pending_workers"] = 0
            self.last_result = copy.deepcopy(report)
            return report
        finally:
            self._lock.release()


def worker(argv):
    if (len(argv) != 4 or argv[0] != "--worker" or argv[2] not in ("1", "2", "3")
            or argv[3] not in ("0", "1")):
        raise ValueError("Exact native Chroma worker arguments required")
    verify_driver(argv[1])
    if not _x86_windows():
        raise RuntimeError("32-bit Windows required")
    branch = next(row for row in BRANCHES if row[0] == int(argv[2]))
    run_branch(ctypes.WinDLL(argv[1]), branch, output_enabled=argv[3] == "1")


if __name__ == "__main__":
    try:
        worker(sys.argv[1:])
    except Exception as error:
        sys.stderr.write(type(error).__name__ + ": " + str(error) + "\n")
        sys.exit(1)
