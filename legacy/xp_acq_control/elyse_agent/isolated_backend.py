"""Cold CardBackend facade with one retained, isolated NI owner process.

Only the runtime NI-owner thread makes RPC calls. Attributes, properties and
isolation_snapshot() use RAM only; GUI/HTTP/telemetry must never poll a process.
No process is spawned until explicit confirmed initialize(). No process is
automatically killed or restarted. Timeout is an UNKNOWN outcome, not cancel,
cleanup or physical OFF. Resources are zero only after successful close AND
confirmed child exit. Python 3.4 compatible; transport uses anonymous pipes.
"""
import copy
import importlib
import math
import os
import queue
import subprocess
import sys
import threading
import time
import uuid

from .isolated_wire import encode_frame, read_frame, write_frame, IsolationProtocolError


OPERATIONS = frozenset(("initialize", "read_snapshot", "general_start", "general_stop",
                       "execute_stage", "execute_impulsion", "set_ht_voltage",
                       "configure_counter_timing", "configure_sync_parameters", "outer_controlled_stop",
                       "execute_cooling_guard", "close"))
CACHED_ATTRIBUTES = frozenset(("resource_count", "procedure", "control_profile",
    "stage_controls_verified", "cooling_trip_verified", "ht_controls_verified",
    "focal_controls_verified", "counter_controls_verified", "ht_voltage_controls_verified",
    "outer_stop_verified", "counter_timing_controls_verified", "ht_feedback_verified",
    "beamline_controls_verified", "ht_sequence_state",
    "ht_zero_tolerance_kv", "ht_zero_timeout", "_stage_simulated", "read_timeout",
    "initial_images", "started_counters", "commanded_digital", "commanded_analog",
    "software_status_assignments", "ht_command_uncertain", "last_cooling_guard",
    "last_impulsion", "last_ht_command", "last_outer_stop", "last_counter_timing",
    "counter_timing_publication", "commanded_counter_ticks", "last_beamline_command",
    "_counter_configuration_uncertain", "initialization_cards", "startup_complete",
    "operator_supervised_test", "operator_test_cold_attested"))


class IsolatedBackendError(RuntimeError):
    """Structured remote error; this never asserts native or physical cleanup."""
    def __init__(self, message, remote_type=None, details=None):
        RuntimeError.__init__(self, message)
        self.remote_type = remote_type
        self.details = copy.deepcopy(details or {})
        for name in ("report", "result", "failures", "error_code", "code"):
            if name in self.details:
                setattr(self, name, copy.deepcopy(self.details[name]))


class IsolatedBackendUncertain(IsolatedBackendError):
    pass


def remote_error(record):
    """Restore only reviewed source cancellation/error classes, never imports
    selected by a remote message. All unknown native errors remain explicit.
    """
    name, message = record.get("type"), record.get("message", "Remote NI failure")
    report, details = record.get("report"), dict(record)
    modules = {
        "AcquisitionCancelled": ("acquisition_backend", False),
        "ProcedureCancelled": ("acquisition_procedures", False),
        "StageExecutionCancelled": ("acquisition_stage_execution", True),
        "StageExecutionError": ("acquisition_stage_execution", True),
        "BeamlineExecutionCancelled": ("acquisition_beamline", True),
        "BeamlineExecutionError": ("acquisition_beamline", True),
        "ImpulsionExecutionCancelled": ("acquisition_impulsion", True),
        "ImpulsionExecutionError": ("acquisition_impulsion", True),
        "HTVoltageCancelled": ("acquisition_ht_voltage", True),
        "HTVoltageError": ("acquisition_ht_voltage", True),
        "CounterTimingCancelled": ("acquisition_counter_timing", True),
        "CounterTimingError": ("acquisition_counter_timing", True),
        "OuterStopExecutionCancelled": ("acquisition_outer_stop", True),
        "OuterStopExecutionError": ("acquisition_outer_stop", True),
    }
    if name == "GeneralStopError" and type(record.get("failures")) in (list, tuple):
        from .acquisition_procedures import GeneralStopError
        return GeneralStopError(record["failures"])
    if name in modules:
        module, needs_report = modules[name]
        try:
            cls = getattr(importlib.import_module("." + module, __package__), name)
            return cls(report if needs_report else message)
        except (ValueError, TypeError, KeyError):
            pass  # Malformed diagnostics cannot turn a failure into success.
    return IsolatedBackendError(name + ": " + message if name else message,
                                remote_type=name, details=details)


class _CachedFocal(object):
    def __init__(self, resources_verified=False):
        self.resources_verified = resources_verified


class IsolatedCardBackend(object):
    isolated_ni_backend = True

    def __init__(self, backend_options=None, focal_options=None, backend_factory=None,
                 rpc_timeout=120.0, close_timeout=10.0, progress_observer=None,
                 safe_sample_budget_seconds=None, python_executable=None):
        for value, maximum in ((rpc_timeout, 600.0), (close_timeout, 120.0)):
            if type(value) not in (int, float) or not math.isfinite(value) or not .05 <= value <= maximum:
                raise ValueError("Finite bounded child RPC timeout required")
        if safe_sample_budget_seconds is not None and (type(safe_sample_budget_seconds) not in (int, float)
                or not math.isfinite(safe_sample_budget_seconds) or not 2 <= safe_sample_budget_seconds <= 30):
            raise ValueError("Conservative safe-sampling budget must be in [2,30] seconds")
        if progress_observer is not None and not callable(progress_observer):
            raise TypeError("Local progress observer must be callable")
        backend_options, focal_options = dict(backend_options or {}), dict(focal_options or {})
        if backend_factory is None:
            factory_name = None
        elif callable(backend_factory):
            module, name = backend_factory.__module__, backend_factory.__name__
            if name == "<lambda>" or "<locals>" in getattr(backend_factory, "__qualname__", name):
                raise ValueError("Child test factory must be a top-level importable callable")
            factory_name = module + ":" + name
        else:
            raise TypeError("Only a trusted local top-level factory is accepted")
        # None deliberately means progress-only. Driver-specific aggregate
        # read budgets must be qualified before sampling inside source waits.
        self._configuration = dict(backend_options=backend_options, focal_options=focal_options,
                                   factory=factory_name, safe_sample_budget_seconds=safe_sample_budget_seconds)
        encode_frame(self._configuration)  # Validate cold values; no native import.
        self._rpc_timeout, self._close_timeout = float(rpc_timeout), float(close_timeout)
        self._observer = progress_observer
        self._python = python_executable or sys.executable
        if python_executable is None and os.path.basename(self._python).lower() == "pythonw.exe":
            self._python = os.path.join(os.path.dirname(self._python), "python.exe")
        if not os.path.isfile(self._python):
            raise ValueError("Explicit child Python executable must exist")
        self._condition = threading.Condition()
        self._write_queue = queue.Queue(maxsize=2)
        self._process = self._reader = self._writer = None
        self._owner_thread = None
        self._active_id = self._active_operation = self._response = self._progress = None
        self._initialization_ready = False
        self._progress_version = 0
        self._software_progress, self._software_version = None, 0
        self._serial = 0
        self._request_started = None
        self._uncertain = self._may_own_resources = self._cleanup_confirmed = False
        self._worker_state, self._worker_error = "COLD", ""
        self._observer_error = ""
        self._worker_pid = None
        self._generation = uuid.uuid4().hex
        self._cache = dict(backend_options, resource_count=0, procedure=None)
        if factory_name is None:
            self._cache.update(startup_complete=False, initialization_cards=None, operator_test_cold_attested=False)
        self._cache.setdefault("control_profile", "legacy_full")
        for name in CACHED_ATTRIBUTES:
            if name.endswith("_verified"):
                self._cache.setdefault(name, False)
        self.focal_command = _CachedFocal(focal_options.get("resources_verified", False))

    @property
    def resource_count(self):
        with self._condition:
            count = self._cache.get("resource_count", 0)
            retained = self._uncertain or self._may_own_resources
        return max(1, count) if retained and not count else count

    def __getattr__(self, name):
        if name not in CACHED_ATTRIBUTES:
            raise AttributeError(name)
        with self._condition:
            if name not in self._cache:
                raise AttributeError(name)
            value = self._cache[name]
        return copy.deepcopy(value)

    def isolation_snapshot(self):
        """RAM-only diagnostics: never poll/wait/read a process or pipe here."""
        with self._condition:
            result = dict(worker_generation=self._generation, worker_pid=self._worker_pid,
                          worker_state=self._worker_state, ownership_uncertain=self._uncertain,
                          cleanup_confirmed=self._cleanup_confirmed, error=self._worker_error,
                          active_request_id=self._active_id, automatic_restart=False,
                          progress_observer_error=self._observer_error,
                          resource_count_interpretation=("UNKNOWN_RETAINED_OWNERSHIP_SENTINEL"
                              if not self._cache.get("resource_count", 0)
                              and (self._uncertain or self._may_own_resources)
                              else "LAST_CHILD_REPORTED_COUNT_NOT_CONTINUOUS_NATIVE_INSPECTION"),
                          hardware_off_confirmed=False)
        result["resource_count"] = self.resource_count
        return result

    def set_execution_observer(self, observer, interval_seconds=.2):
        if observer is not None and not callable(observer):
            raise TypeError("Local progress observer must be callable")
        self._observer = observer

    def _mark_uncertain(self, reason):
        with self._condition:
            if self._cleanup_confirmed:
                return
            self._uncertain = self._may_own_resources = True
            self._worker_state, self._worker_error = "OWNERSHIP_UNCERTAIN", str(reason)
            self._condition.notify_all()

    def _spawn(self):
        if self._process is not None:
            raise IsolatedBackendUncertain("Child owner cannot be replaced or reinitialized")
        self._owner_thread = threading.current_thread().ident
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isolated_worker.py")
        options = dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        if os.name == "nt":
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
            options.update(startupinfo=startup, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(os.path.abspath(path or os.curdir) for path in sys.path)
        options["env"] = environment
        self._process = subprocess.Popen([self._python, "-u", path], **options)
        with self._condition:
            self._worker_pid = self._process.pid
            self._worker_state = "SPAWNED_UNINITIALIZED"
            self._may_own_resources = True
        self._writer = threading.Thread(target=self._write_loop, name="ACQ-NI-IPC-writer")
        self._reader = threading.Thread(target=self._read_loop, name="ACQ-NI-IPC-reader")
        self._writer.daemon = self._reader.daemon = True
        self._writer.start()
        self._reader.start()

    def _write_loop(self):
        while True:
            message = self._write_queue.get()
            if message is None:
                return
            try:
                write_frame(self._process.stdin, message)
            except Exception as error:
                self._mark_uncertain("Child pipe write: " + str(error))
                return

    def _read_loop(self):
        try:
            while True:
                message = read_frame(self._process.stdout)
                if message.get("kind") == "initialization_status":
                    attributes = message.get("attributes")
                    if (set(message) != {"kind", "attributes"} or type(attributes) is not dict
                            or set(attributes) != {"initialization_cards", "startup_complete", "resource_count"}
                            or type(attributes["initialization_cards"]) is not dict
                            or attributes["startup_complete"] is not False
                            or type(attributes["resource_count"]) is not int or attributes["resource_count"] < 0):
                        raise IsolationProtocolError("Invalid retained initialization status")
                    with self._condition:
                        if self._cleanup_confirmed:
                            raise IsolationProtocolError("Initialization status after confirmed release")
                        self._cache.update(attributes)
                        self._condition.notify_all()
                    continue  # Never changes runtime state, readiness or measurements.
                if message.get("kind") not in ("result", "progress", "initialize_ready") or type(message.get("id")) is not int:
                    raise IsolationProtocolError("Unexpected child message")
                attributes = message.get("attributes", {})
                if type(attributes) is not dict or any(name not in CACHED_ATTRIBUTES for name in attributes):
                    raise IsolationProtocolError("Unexpected child attribute")
                if "resource_count" in attributes and (type(attributes["resource_count"]) is not int
                                                         or attributes["resource_count"] < 0):
                    raise IsolationProtocolError("Invalid child resource count")
                with self._condition:
                    if message["id"] != self._active_id:
                        raise IsolationProtocolError("Unexpected child request ID")
                    if message["kind"] == "initialize_ready":
                        if (self._active_operation != "initialize" or self._initialization_ready
                                or set(message) != {"kind", "id", "attributes"}
                                or attributes != {"resource_count": 0}):
                            raise IsolationProtocolError("Unexpected dependency-ready handshake")
                        self._initialization_ready = True
                        self._condition.notify_all()
                        continue
                    self._cache.update(attributes)
                    if message["kind"] == "result":
                        self._response = message
                    else:
                        event = message.get("event")
                        if type(event) is dict:
                            event.update(parent_received_monotonic=time.monotonic(),
                                worker_generation=self._generation, rpc_request_id=message["id"],
                                rpc_operation=self._active_operation,
                                parent_request_started_monotonic=self._request_started)
                        if type(event) is dict and event.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
                            self._software_progress = event
                            self._software_version += 1
                        else:
                            self._progress = event
                            self._progress_version += 1
                    self._condition.notify_all()
        except Exception as error:
            self._mark_uncertain("Child pipe closed or invalid: " + str(error))

    def _queue(self, message):
        encode_frame(message)  # Bound before giving a writer a pipe operation.
        try:
            self._write_queue.put_nowait(message)
        except queue.Full:
            self._mark_uncertain("Bounded child IPC write queue exhausted")
            raise IsolatedBackendUncertain("Child IPC queue exhausted; outcome unknown")

    def _assert_owner(self):
        if self._owner_thread != threading.current_thread().ident:
            raise RuntimeError("Only the original runtime NI-owner thread may call child RPC")

    def _observe_progress(self, event):
        if event is None or self._observer is None:
            return
        try:
            notice = copy.deepcopy(event)
            if type(notice) is dict and "sample" in notice:
                age, received = notice.get("sample_age_seconds"), notice.get("parent_received_monotonic")
                if (type(age) in (int, float) and math.isfinite(age) and age >= 0
                        and type(received) in (int, float) and math.isfinite(received)):
                    notice["sample_age_seconds"] = age + max(0., time.monotonic() - received)
            if type(notice) is dict and notice.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
                age, received = notice.get("software_state_age_seconds", 0.), notice.get("parent_received_monotonic")
                if (type(age) in (int, float) and math.isfinite(age) and age >= 0
                        and type(received) in (int, float) and math.isfinite(received)):
                    notice["software_state_age_seconds"] = age + max(0., time.monotonic() - received)
            if type(notice) is dict:
                # Request-relative child durations are comparable to parent
                # durations; absolute process-local monotonic epochs are not.
                # Parent send precedes child entry, so this is conservative
                # even under pipe backpressure or delayed IPC decoding.
                start = notice.get("parent_request_started_monotonic")
                is_sample = "sample" in notice
                is_software = notice.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT"
                offset_field = ("sample_started_after_request_seconds" if is_sample
                                else "software_observed_after_request_seconds")
                offset = notice.get(offset_field)
                age_field = "sample_age_seconds" if is_sample else "software_state_age_seconds"
                if (is_sample or is_software) and (self._active_id is not None
                        or "parent_request_started_monotonic" in notice):
                    observation = notice.get("observation_after_request_seconds")
                    age = notice.get(age_field)
                    def finite(value):
                        return type(value) in (int, float) and math.isfinite(value)
                    elapsed = time.monotonic() - start if finite(start) else None
                    valid = (finite(elapsed) and elapsed >= 0 and finite(offset)
                             and 0 <= offset <= elapsed and finite(observation)
                             and offset <= observation <= elapsed and finite(age) and age >= 0)
                    if valid:
                        notice[age_field] = max(age, max(0., elapsed - offset))
                    elif is_sample:
                        notice.pop("sample", None)
                        notice["sample_error"] = dict(type="InvalidSamplingProvenance",
                            message="Missing or invalid request-relative age proof; sample unavailable")
                    else:
                        notice[age_field] = None
            self._observer(notice)  # NI caller only, never the IPC reader.
        except Exception as error:
            # Observability must not abandon an in-flight native call or turn
            # a source dwell into a skipped pulse restoration.
            self._observer_error = type(error).__name__ + ": " + str(error)

    def _rpc(self, operation, arguments=(), keywords=None, cancel=None, timeout=None):
        if operation not in OPERATIONS:
            raise ValueError("Operation is not on the private NI allowlist")
        self._assert_owner()
        with self._condition:
            if self._uncertain and operation != "close":
                raise IsolatedBackendUncertain("Prior unknown outcome blocks further native operations")
            if self._active_id is not None:
                if operation == "close" and self._response is not None:
                    self._active_id = self._active_operation = self._response = self._progress = None
                else:
                    raise IsolatedBackendUncertain("Prior child call unresolved; cleanup cannot race it")
            if self._cleanup_confirmed:
                raise RuntimeError("Released NI owner cannot execute another operation")
            self._serial += 1
            self._request_started = time.monotonic()
            request_id = self._active_id = self._serial
            self._active_operation = operation
            seen_progress = self._progress_version
            seen_software = self._software_version
            self._worker_state = "EXECUTING_" + operation.upper()
        message = dict(kind="call", id=request_id, operation=operation,
                       arguments=tuple(arguments), keywords=dict(keywords or {}))
        if operation == "initialize":
            message["configuration"] = self._configuration
        try:
            self._queue(message)
        except IsolationProtocolError:
            # Validation failed before any bytes entered the IPC writer. Do
            # not invent an active native operation that can never answer.
            with self._condition:
                self._active_id = self._active_operation = None
                self._worker_state = "IDLE_OWNED"
            raise
        deadline = time.monotonic() + (self._rpc_timeout if timeout is None else timeout)
        cancellation_sent = activation_sent = False
        while True:
            event, software_event, response = None, None, None
            with self._condition:
                response = self._response
                expired = time.monotonic() >= deadline
                if response is None and not expired:
                    self._condition.wait(min(.02, max(0, deadline - time.monotonic())))
                response = self._response
                expired = time.monotonic() >= deadline
                if self._progress_version != seen_progress:
                    event, seen_progress = self._progress, self._progress_version
                if self._software_version != seen_software:
                    software_event, seen_software = self._software_progress, self._software_version
            self._observe_progress(software_event)
            self._observe_progress(event)
            if response is not None:
                with self._condition:
                    self._active_id = self._active_operation = self._response = self._progress = None
                    if not self._uncertain:
                        self._worker_state = "IDLE_OWNED"
                if response.get("ok") is not True:
                    raise remote_error(response.get("error", {}))
                return response.get("value")
            if expired:
                self._mark_uncertain("RPC deadline exceeded for " + operation + "; outcome UNKNOWN")
                raise IsolatedBackendUncertain("Child RPC timeout for " + operation + "; outcome UNKNOWN")
            if operation == "initialize" and self._initialization_ready and not activation_sent:
                # Dependencies are ready, but no Task call has been admitted.
                # A cancellation queued during imports reaches the child on
                # its main thread before it can begin native initialization.
                self._queue(dict(kind="activate_initialize", id=request_id,
                                 cancelled=bool(cancel is not None and cancel.is_set())))
                activation_sent = True
            if cancel is not None and cancel.is_set() and not cancellation_sent:
                self._queue(dict(kind="cancel", id=request_id))
                cancellation_sent = True
            with self._condition:
                if self._uncertain:
                    raise IsolatedBackendUncertain(self._worker_error)

    def initialize(self, cancel, startup_confirmed=False):
        if startup_confirmed is not True:
            raise ValueError("Explicit local confirmation of NI startup required")
        if cancel.is_set():
            from .acquisition_backend import AcquisitionCancelled
            raise AcquisitionCancelled()
        self._spawn()
        return self._rpc("initialize", keywords=dict(startup_confirmed=True), cancel=cancel)

    def read_snapshot(self, cancel):
        return self._rpc("read_snapshot", cancel=cancel)

    def general_start(self, cancel, operator_confirmed=False):
        return self._rpc("general_start", keywords=dict(operator_confirmed=operator_confirmed), cancel=cancel)

    def general_stop(self, operator_confirmed=False):
        return self._rpc("general_stop", keywords=dict(operator_confirmed=operator_confirmed))

    def execute_stage(self, operation, cancel, operator_confirmed=False, new_value=True):
        return self._rpc("execute_stage", (operation,),
                         dict(operator_confirmed=operator_confirmed, new_value=new_value), cancel)

    def execute_impulsion(self, operation, cancel, operator_confirmed=False, new_value=True):
        return self._rpc("execute_impulsion", (operation,),
                         dict(operator_confirmed=operator_confirmed, new_value=new_value), cancel)

    def set_ht_voltage(self, command_kv, cancel, operator_confirmed=False):
        return self._rpc("set_ht_voltage", (command_kv,), dict(operator_confirmed=operator_confirmed), cancel)

    def configure_counter_timing(self, snapshot, cancel, operator_confirmed=False):
        return self._rpc("configure_counter_timing", (snapshot,),
                         dict(operator_confirmed=operator_confirmed), cancel)

    def configure_sync_parameters(self, value, cancel, operator_confirmed=False):
        return self._rpc("configure_sync_parameters", (value,),
                         dict(operator_confirmed=operator_confirmed), cancel)

    def execute_cooling_guard(self, snapshot, cancel):
        return self._rpc("execute_cooling_guard", (snapshot,), cancel=cancel)

    def outer_controlled_stop(self, operator_confirmed=False):
        return self._rpc("outer_controlled_stop", keywords=dict(operator_confirmed=operator_confirmed))

    def close(self):
        if self._process is None:
            return  # Cold facade has never created a process or NI owner.
        if self._cleanup_confirmed:
            return
        with self._condition:
            late_close = (self._active_operation == "close" and self._response is not None
                          and self._response.get("ok") is True)
            if late_close:
                self._active_id = self._active_operation = self._response = self._progress = None
        if not late_close:
            self._rpc("close", timeout=self._close_timeout)
        with self._condition:
            released = self._cache.get("resource_count") == 0
        if not released:
            self._mark_uncertain("Cleanup returned but child still owns resources")
            raise IsolatedBackendUncertain("Child cleanup did not confirm zero resources")
        try:
            code = self._process.wait(timeout=self._close_timeout)
        except subprocess.TimeoutExpired:
            self._mark_uncertain("Cleanup returned but child exit/join is unconfirmed")
            raise IsolatedBackendUncertain("Child cleanup exit/join timeout; ownership retained")
        if code != 0:
            self._mark_uncertain("Child exited abnormally after cleanup")
            raise IsolatedBackendUncertain("Abnormal child exit; ownership retained")
        with self._condition:
            self._cache["resource_count"] = 0
            self._cleanup_confirmed = True
            self._uncertain = self._may_own_resources = False
            self._worker_state, self._worker_error = "CLOSED_JOINED", ""
        self._write_queue.put_nowait(None)
        for stream in (self._process.stdin, self._process.stdout):
            stream.close()
