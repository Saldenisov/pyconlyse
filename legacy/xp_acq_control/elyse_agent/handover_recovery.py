"""Explicit local VI-to-Python handover verification; Python 3.4, no NI I/O.

Toolhelp PROCESS metadata establishes only point-in-time process absence.
It does not establish electrical OFF, release of NI tasks, absence of unknown
DAQ clients, or a machine-wide lock. Those first two facts require a current
local operator attestation. LabVIEW may remain open with its VI stopped.

Nothing here deletes markers, starts/stops processes, imports NI, enumerates
modules, initializes cards, or authorizes automatic recovery. The caller must
retain the original marker in an audit backup and use OwnershipMarker.recover
only inside local_confirmation after displaying the exact confirmation text.
"""
import contextlib
import ctypes
import json
import math
import os
import sys
import threading
import time

from .acquisition_recovery import OwnershipMarker, RecoveryRequired


HANDOVER_CONFIRMATION = (
    "Acquisition VI is stopped; ALL external NI tasks have been released; "
    "the installation is electrically OFF."
)
CONFIRMATION_TTL_SECONDS = 60.0
INVENTORY_MAX_AGE_SECONDS = 15.0
MAX_PROCESS_ROWS = 4096
_KNOWN_DAQ_CLIENTS = frozenset((
    "nimax.exe", "max.exe", "nimaxexeserver.exe", "nidaq.exe", "nidaq32.exe",
    "nidaqmx.exe", "nitestpanels.exe", "testpanels.exe",
))


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def windows_process_inventory():
    """Read XP x86 PROCESSENTRY32W only; do not request module snapshots.

    Access denial, partial collection, excessive rows, and abnormal iteration
    termination all raise. No protected process needs to be opened.
    """
    if (sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 4
            or tuple(sys.getwindowsversion()[:2]) != (5, 1)):
        raise RecoveryRequired("Local handover verifier requires Windows XP x86")
    from ctypes import wintypes as w

    class Process(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
                    ("heap", ctypes.c_void_p), ("module", w.DWORD), ("threads", w.DWORD),
                    ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
                    ("name", w.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (w.DWORD, w.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    kernel.Process32FirstW.argtypes = (w.HANDLE, ctypes.POINTER(Process))
    kernel.Process32FirstW.restype = w.BOOL
    kernel.Process32NextW.argtypes = (w.HANDLE, ctypes.POINTER(Process))
    kernel.Process32NextW.restype = w.BOOL
    kernel.CloseHandle.argtypes = (w.HANDLE,)
    kernel.CloseHandle.restype = w.BOOL
    observed = time.monotonic()
    handle = kernel.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS only.
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = Process()
        entry.size = ctypes.sizeof(Process)
        if not kernel.Process32FirstW(handle, ctypes.byref(entry)):
            raise ctypes.WinError(ctypes.get_last_error())
        rows = []
        while True:
            if len(rows) >= MAX_PROCESS_ROWS:
                raise RecoveryRequired("Process inventory exceeds reviewed bound")
            rows.append(dict(pid=int(entry.pid), parent=int(entry.parent), name=entry.name))
            if not kernel.Process32NextW(handle, ctypes.byref(entry)):
                if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES only.
                    raise ctypes.WinError(ctypes.get_last_error())
                break
        return dict(processes=rows, pid=os.getpid(), observed_monotonic=observed)
    finally:
        kernel.CloseHandle(handle)


class LocalHandoverVerifier(object):
    """Checker for OwnershipMarker, enabled only by same-thread local consent.

    inventory is an injected callable returning a fresh complete PROCESS
    snapshot: {pid, observed_monotonic, processes: [{pid, parent, name}, ...]}.
    Synthetic inventory is the only supported test seam; production uses the
    XP x86 Toolhelp reader. clock must use that snapshot's monotonic domain.
    """
    def __init__(self, process_id=None, inventory=None, clock=None):
        self.process_id = os.getpid() if process_id is None else process_id
        if type(self.process_id) is not int or self.process_id <= 0:
            raise ValueError("Positive current process identifier required")
        if inventory is not None and not callable(inventory):
            raise ValueError("Process inventory must be callable")
        if clock is not None and not callable(clock):
            raise ValueError("Monotonic clock must be callable")
        self._inventory = windows_process_inventory if inventory is None else inventory
        self._clock = time.monotonic if clock is None else clock
        self._lock = threading.RLock()
        self._confirmation = None

    def _now(self):
        try:
            now = self._clock()
        except Exception as error:
            raise RecoveryRequired("Local handover clock unavailable: " + str(error))
        if not _finite_number(now) or now < 0:
            raise RecoveryRequired("Valid monotonic handover timestamp required")
        return now

    @contextlib.contextmanager
    def local_confirmation(self, confirmation, operator):
        """Scope explicit LOCAL UI consent; never call from remote commands.

        Scope expires after 60 s and cannot be nested or used from another
        thread. The verifier rechecks it after inventory collection as well.
        """
        if confirmation != HANDOVER_CONFIRMATION or not isinstance(confirmation, str):
            raise ValueError("Exact local VI/tasks/electrical OFF confirmation required")
        if (not isinstance(operator, str) or not operator.strip() or len(operator) > 160
                or any(ord(character) < 32 for character in operator)):
            raise ValueError("Identified local operator required")
        token = object()
        with self._lock:
            if self._confirmation is not None:
                raise RecoveryRequired("A local handover confirmation is already active")
            self._confirmation = dict(token=token, thread=threading.current_thread(),
                                      acknowledged=self._now(), operator=operator.strip())
        try:
            yield self
        finally:
            with self._lock:
                if self._confirmation is not None and self._confirmation["token"] is token:
                    self._confirmation = None

    def _acknowledgement(self):
        with self._lock:
            ack = self._confirmation
            if ack is None or ack["thread"] is not threading.current_thread():
                raise RecoveryRequired("Current same-thread LOCAL operator confirmation required")
            age = self._now() - ack["acknowledged"]
            if age < 0 or age > CONFIRMATION_TTL_SECONDS:
                raise RecoveryRequired("Local operator handover confirmation expired or clock reversed")
            return dict(ack)

    def __call__(self, prior_marker):
        """Return bounded evidence; caller remains responsible for marker audit.

        Required legacy bool fields combine process evidence and the explicit
        operator attestation. They are not independent driver/physical probes.
        Additional fields identify exactly which observations support them.
        """
        ack = self._acknowledgement()
        try:
            if not isinstance(prior_marker, dict):
                raise ValueError("Marker must be an object")
            marker = OwnershipMarker._decode(json.dumps(prior_marker).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError, RecoveryRequired):
            raise RecoveryRequired("Qualified prior ownership marker required; preserved")
        if marker["owner_pid"] == self.process_id:
            raise RecoveryRequired("Prior owner PID equals current process; identity is ambiguous")
        try:
            snapshot = self._inventory()
        except Exception as error:
            raise RecoveryRequired("Complete process inventory unavailable: " + str(error))
        after = self._acknowledgement()
        if after["token"] is not ack["token"]:
            raise RecoveryRequired("Local handover confirmation changed during verification")
        if (not isinstance(snapshot, dict)
                or set(snapshot) != {"pid", "observed_monotonic", "processes"}
                or type(snapshot["pid"]) is not int or snapshot["pid"] != self.process_id
                or not _finite_number(snapshot["observed_monotonic"])):
            raise RecoveryRequired("Complete current-process inventory metadata required")
        observed = snapshot["observed_monotonic"]
        age = self._now() - observed
        if age < 0 or age > INVENTORY_MAX_AGE_SECONDS:
            raise RecoveryRequired("Process inventory is stale or clock reversed")
        rows = snapshot["processes"]
        if type(rows) is not list or not rows or len(rows) > MAX_PROCESS_ROWS:
            raise RecoveryRequired("Nonempty bounded process inventory required")
        seen, blocked, labview = set(), [], []
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"pid", "parent", "name"}
                    or type(row["pid"]) is not int or not 0 <= row["pid"] <= 0xffffffff
                    or type(row["parent"]) is not int or not 0 <= row["parent"] <= 0xffffffff
                    or not isinstance(row["name"], str) or not row["name"]
                    or row["name"] != row["name"].strip() or len(row["name"]) > 260
                    or any(character in row["name"] for character in ("\x00", "/", "\\"))
                    or any(ord(character) < 32 for character in row["name"])):
                raise RecoveryRequired("Malformed process inventory row")
            pid, name = row["pid"], row["name"].lower()
            if pid in seen:
                raise RecoveryRequired("Duplicate process identifier in inventory")
            seen.add(pid)
            if pid == marker["owner_pid"]:
                blocked.append("{0}:{1} (prior owner PID present or reused)".format(pid, name))
            if pid != self.process_id and ("python" in name or name in ("py.exe", "pyw.exe")):
                blocked.append("{0}:{1} (possible retained native worker)".format(pid, name))
            if (name in _KNOWN_DAQ_CLIENTS or "daqmx" in name
                    or name.startswith("nidaq") and name.endswith(".exe")):
                blocked.append("{0}:{1} (known MAX/DAQ client)".format(pid, name))
            if name == "labview.exe":
                labview.append(pid)
        if self.process_id not in seen:
            raise RecoveryRequired("Current server missing from process inventory")
        if blocked:
            raise RecoveryRequired("Handover blocked by process inventory: " + "; ".join(blocked)[:1800])
        self._acknowledgement()  # Validation itself must fit the local consent window.
        return dict(
            verified=True, owner_process_absent=True, native_children_absent=True,
            ni_competitors_absent=True,
            method=("Explicit current local operator attestation of stopped Acquisition VI, "
                    "released external NI tasks and electrical OFF, plus fresh XP x86 "
                    "Toolhelp PROCESS inventory; point-in-time only, not an NI task probe "
                    "or universal hardware lock"),
            evidence_scope="local_operator_attestation_plus_point_in_time_process_inventory",
            process_inventory=dict(observed_monotonic=observed, age_seconds=age,
                                   process_count=len(rows), prior_owner_pid=marker["owner_pid"],
                                   other_python_processes_absent=True,
                                   known_max_daq_clients_absent=True,
                                   labview_processes_left_open=labview),
            operator_attestation=dict(operator=ack["operator"], confirmation=HANDOVER_CONFIRMATION,
                                      acknowledged_monotonic=ack["acknowledged"],
                                      acquisition_vi_stopped=True, external_ni_tasks_released=True,
                                      electrical_off=True),
            ni_task_release_independently_verified=False,
            electrical_off_independently_verified=False,
            universal_ni_exclusion_established=False, hardware_commands_sent=False)
