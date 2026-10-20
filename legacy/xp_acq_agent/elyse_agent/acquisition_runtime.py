"""One NI owner thread; cold startup, explicit init/deinit, latest-only RAM.

Stop requests do not close tasks concurrently with a DAQmx read. Cleanup errors
retain ownership, prevent reinitialization/exit and allow an explicit retry.
"""
import copy
import datetime
import threading
import time

from .acquisition_backend import AcquisitionCancelled
from .acquisition_procedures import ProcedureCancelled
from .acquisition_stage_execution import (
    SUPPORTED_OPERATIONS, StageExecutionCancelled,
)
from .acquisition_stage_model import cooling_flow_trip


class AcquisitionRuntime(object):
    def __init__(self, backend_factory, period=0.2, clock=None):
        if not 0.02 <= period <= 10:
            raise ValueError("invalid read period")
        self._factory = backend_factory
        self._period = period
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._cancel = threading.Event()
        self._thread = None
        self._backend = None
        self._pending = None
        self._shutdown_requested = False
        self._state = "IDLE"
        self._error = ""
        self._latest = None
        self._received_at = None
        self._sequence = 0
        self._everest_seen = None
        self._operation = None
        self._general_stop_required = False
        self._stage_command = None

    @staticmethod
    def _stop_in_progress(operation):
        return (operation == "modulator.general.stop"
                or operation == "acq.timeout.cooling_trip"
                or (isinstance(operation, str) and operation.startswith("acq.stage.")
                    and operation.endswith(".stop")))

    def stage_request(self, operation, operator_confirmed=False, new_value=True):
        """Local only; an accepted procedure runs on the existing NI owner.

        Commissioning is independent of source EPS flags and off by default.
        This API does not add an HTTP/Tango command or a GUI activation button.
        """
        if operation not in SUPPORTED_OPERATIONS or type(new_value) is not bool:
            raise ValueError("Reviewed stage operation and Boolean NewVal required")
        if operator_confirmed is not True:
            raise ValueError("Explicit local stage confirmation required")
        if not new_value:
            return False  # The saved False NewVal arm has no effects.
        with self._lock:
            permitted_states = ("RUNNING", "FAULT") if operation.endswith(".stop") else ("RUNNING",)
            if (self._backend is None or not self._backend.resource_count
                    or self._state not in permitted_states or self._pending is not None
                    or self._shutdown_requested or self._operation is not None):
                raise RuntimeError("Stage execution requires idle existing card ownership")
            if (getattr(self._backend, "stage_controls_verified", False) is not True
                    or getattr(self._backend, "control_profile", None) == "general_only_test"):
                raise RuntimeError("Stage controls are not commissioned for this backend")
            self._stage_command = operation
            self._pending = "stage"
            self._operation = "acq.stage." + operation
            self._state = "EXECUTING"
            self._received_at = None  # A precommand input image is not fresh postcommand data.
            self._general_stop_required = True
            self._wake.set()
            return True

    def general_start(self, operator_confirmed=False):
        with self._lock:
            if operator_confirmed is not True:
                raise ValueError("Explicit local General Marche confirmation required")
            if self._state != "RUNNING" or self._pending is not None or self._shutdown_requested:
                raise RuntimeError("General Marche requires RUNNING and no pending procedure")
            self._state = "EXECUTING"
            self._operation = "modulator.general.start"
            self._general_stop_required = True
            self._pending = "general_start"
            self._wake.set()

    def general_stop(self, operator_confirmed=False):
        with self._lock:
            if operator_confirmed is not True:
                raise ValueError("Explicit local General Arret confirmation required")
            if (self._backend is None or not self._backend.resource_count or self._shutdown_requested
                    or self._pending not in (None, "general_start", "stage")
                    or self._state not in ("RUNNING", "FAULT", "EXECUTING")
                    or (self._state == "EXECUTING"
                        and (self._stop_in_progress(self._operation)
                             or not (self._operation == "modulator.general.start"
                                     or (isinstance(self._operation, str)
                                         and self._operation.startswith("acq.stage.")))))):
                raise RuntimeError("General Arret requires existing card ownership and no pending cleanup")
            # Interrupt a read/start, restore its asserted pulse, then stop on
            # the SAME owner. Never close/reopen/reinitialize tasks here.
            self._cancel.set()
            self._general_stop_required = True
            self._state = "EXECUTING"
            self._operation = "modulator.general.stop"
            self._pending = "general_stop"
            self._stage_command = None
            self._wake.set()

    def start(self):
        with self._lock:
            if self._thread is not None:
                raise RuntimeError("Server worker already started")
            self._thread = threading.Thread(target=self._run, name="ACQ-card-owner")
            self._thread.daemon = False
            self._thread.start()

    def initialize(self, startup_confirmed=False):
        with self._lock:
            if startup_confirmed is not True:
                raise ValueError("Local operator startup confirmation required")
            if self._state != "IDLE" or self._shutdown_requested:
                raise RuntimeError("Initialization requires IDLE")
            self._state = "INITIALIZING"
            self._error = ""
            self._latest = self._received_at = None
            self._cancel.clear()
            self._pending = "initialize"
            self._wake.set()

    def _check_release(self, electrical_off_confirmed):
        if self._stop_in_progress(self._operation) or self._pending == "general_stop":
            raise RuntimeError("Wait for stop procedure to finish; NI ownership must be retained")
        if self._general_stop_required and electrical_off_confirmed is not True:
            raise RuntimeError("Execute General Arret first, or confirm cabinet switched off locally")
        if electrical_off_confirmed is True:
            self._general_stop_required = False

    def deinitialize(self, electrical_off_confirmed=False):
        with self._lock:
            if self._state == "STOPPED":
                return
            self._check_release(electrical_off_confirmed)
            self._cancel.set()
            self._state = "DEINITIALIZING"
            self._pending = "close"
            self._wake.set()

    def request_shutdown(self, electrical_off_confirmed=False):
        with self._lock:
            if self._state == "STOPPED":
                return
            self._check_release(electrical_off_confirmed)
            self._shutdown_requested = True
            self._cancel.set()
            self._state = "DEINITIALIZING"
            self._pending = "close"
            self._wake.set()

    def note_everest_read(self):
        with self._lock:
            self._everest_seen = self._clock()

    def snapshot(self):
        with self._lock:
            now = self._clock()
            age = None if self._received_at is None else max(0.0, now - self._received_at)
            return dict(
                state=self._state, error=self._error,
                current_operation=self._operation,
                general_stop_required=self._general_stop_required,
                procedure=copy.deepcopy(getattr(self._backend, "procedure", None)),
                control_profile=getattr(self._backend, "control_profile", None),
                sequence=self._sequence, latest=copy.deepcopy(self._latest),
                age_seconds=age,
                stale=self._state != "RUNNING" or age is None or age > 2,
                resource_count=self._backend.resource_count if self._backend is not None else 0,
                everest_read_age_seconds=(None if self._everest_seen is None
                                         else max(0.0, now - self._everest_seen)),
                storage_mode="ram_latest", auto_initialize=False,
                deinitialize_means="Release NI tasks, not electrical emergency stop",
                remote_initialization_enabled=False, remote_setpoints_enabled=False,
                stage_execution=dict(implemented=list(SUPPORTED_OPERATIONS),
                                     commissioned=getattr(self._backend, "stage_controls_verified", False) is True,
                                     cooling_trip_commissioned=getattr(self._backend, "cooling_trip_verified", False) is True,
                                     remote_commands_enabled=False),
            )

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)
            return not self._thread.is_alive()
        return True

    def _close(self, error=""):
        try:
            if self._backend is not None:
                self._backend.close()
        except Exception as cleanup_error:
            with self._lock:
                self._error = (error + "; " if error else "") + "Cleanup: " + str(cleanup_error)
                self._state = "FAULT"
                self._shutdown_requested = False
            return False
        with self._lock:
            self._backend = None
            self._operation = None
            self._error = error
            self._state = "FAULT" if error else "STOPPED" if self._shutdown_requested else "IDLE"
        return True

    def _procedure_fault(self, error):
        # An output may already have changed. Releasing NI tasks is NOT a
        # substitute for electrical stop; keep the same owner for Arret/retry.
        with self._lock:
            self._error = type(error).__name__ + ": " + str(error)
            self._state = "FAULT"
            self._operation = None
            # A separately confirmed local OFF/close request still belongs to
            # this owner. Do not strand a shutdown as IDLE after start failure.
            if self._pending != "close":
                self._shutdown_requested = False

    def _finish_stage(self):
        with self._lock:
            if self._pending is None and not self._cancel.is_set():
                self._error = ""
                self._operation = None
                self._state = "RUNNING"

    def _run_cooling_guard(self, latest):
        """Consume the successful owner read; never infer a heating permit."""
        with self._lock:
            if (self._state != "RUNNING" or self._pending is not None or self._cancel.is_set()
                    or getattr(self._backend, "stage_controls_verified", False) is not True
                    or getattr(self._backend, "cooling_trip_verified", False) is not True
                    or getattr(self._backend, "_stage_simulated", False) is True
                    or getattr(self._backend, "control_profile", None) == "general_only_test"):
                return
            banks = latest["banks"]
            if not cooling_flow_trip(banks["C4_DIO96_DI"]["values"], banks["C3_DIO96_DI"]["values"]):
                return
            self._general_stop_required = True
            self._state = "EXECUTING"
            self._operation = "acq.timeout.cooling_trip"
            self._received_at = None
        self._backend.execute_cooling_guard(latest, self._cancel)
        self._finish_stage()

    def _run(self):
        while True:
            with self._lock:
                pending, self._pending = self._pending, None
                stage_command = self._stage_command if pending == "stage" else None
                if pending == "stage":
                    self._stage_command = None
                running = self._state == "RUNNING"
            if pending == "initialize":
                try:
                    self._backend = self._factory()
                    self._backend.initialize(self._cancel, startup_confirmed=True)
                    with self._lock:
                        if not self._cancel.is_set():
                            self._state = "RUNNING"
                except AcquisitionCancelled:
                    self._close()
                except Exception as error:
                    self._close(type(error).__name__ + ": " + str(error))
            elif pending == "close":
                self._close()
            elif pending == "general_start":
                try:
                    self._backend.general_start(self._cancel, operator_confirmed=True)
                    with self._lock:
                        if not self._cancel.is_set():
                            self._operation = None
                            self._state = "RUNNING"
                except ProcedureCancelled:
                    pass  # Pending deinit/shutdown is handled by this owner.
                except Exception as error:
                    self._procedure_fault(error)
            elif pending == "general_stop":
                with self._lock:
                    self._state = "EXECUTING"
                    self._operation = "modulator.general.stop"
                try:
                    self._backend.general_stop(operator_confirmed=True)
                    with self._lock:
                        self._general_stop_required = False
                        self._cancel.clear()
                        self._error = ""
                        self._operation = None
                        self._state = "RUNNING"
                except Exception as error:
                    self._procedure_fault(error)
            elif pending == "stage":
                try:
                    with self._lock:
                        if (self._pending is None and not self._shutdown_requested
                                and self._operation == "acq.stage." + stage_command):
                            # Clear cancellation retained by a failed older
                            # procedure only on the owner, never over a newly
                            # queued General stop/confirmed close.
                            self._cancel.clear()
                    self._backend.execute_stage(stage_command, self._cancel, operator_confirmed=True)
                    self._finish_stage()
                except StageExecutionCancelled as error:
                    # The executor has attempted pulse restoration. Preserve
                    # a queued General stop/confirmed close on this owner.
                    with self._lock:
                        pending_recovery = self._pending is not None
                    if not pending_recovery:
                        self._procedure_fault(error)
                except Exception as error:
                    self._procedure_fault(error)
            elif running:
                try:
                    latest = self._backend.read_snapshot(self._cancel)
                    with self._lock:
                        if not self._cancel.is_set() and self._state == "RUNNING" and self._pending is None:
                            self._sequence += 1
                            self._latest = copy.deepcopy(latest)
                            self._latest["received_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            self._received_at = self._clock()
                    self._run_cooling_guard(latest)
                except AcquisitionCancelled:
                    pass  # Pending close is processed on this same owner thread.
                except Exception as error:
                    if self._general_stop_required:
                        self._procedure_fault(error)
                    else:
                        self._close(type(error).__name__ + ": " + str(error))
            with self._lock:
                if self._state == "STOPPED":
                    return
            self._wake.wait(self._period)
            self._wake.clear()
