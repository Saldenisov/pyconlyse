"""Separate control-capable runtime; preserves the original read-only service.

Remote methods enqueue on the existing NI owner, never execute on HTTP/Tango
threads. Native execution is observed explicitly; accepted != completed !=
physical acknowledgement. No remote initialization, cleanup or process exit.
"""
import hashlib
import os
import threading
import uuid
import copy
import datetime
import time
import math
from functools import wraps

from .acquisition_runtime import AcquisitionRuntime
from .command_broker import CommandBroker
from .cooling_safety import CoolingSafety, decode_publications, runtime_publications
from .chroma_focal_stop import BRANCHES
from .runtime_identity import SOURCE_PATHS
from .control_policy import require_command, command_capabilities, BEAMLINE_OPERATIONS
from .cooling_startup import wait_for_cooling
from .hardware_plan import AI_BANKS, DI_BANKS
from .acquisition_procedures import ProcedureCancelled
from .acquisition_backend import AcquisitionCancelled


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False

CONTROL_MODULES = ("acquisition_remote.py", "acquisition_control_runtime.py",
                   "acquisition_control_gui.py", "cooling_safety.py",
                   "acquisition_driver_diagnostics.py", "control_policy.py", "cooling_startup.py")
CONTROL_MODULES += ("native_telemetry.py", "shared_state.py", "labview_telemetry.py",
                    "telemetry_relay.py", "protocol.py", "supervision_wire.py", "errors.py",
                    "dual_mode_telemetry.py", "shared_state_receiver.py")
CONTROL_MODULES += ("command_protocol.py", "command_broker.py", "command_http.py", "command_dispatch.py",
                    "standard_banks.py", "telemetry_publisher.py", "telemetry_view.py", "application_view.py",
                    "journal_worker.py", "isolated_backend.py", "isolated_wire.py", "isolated_worker.py")
CONTROL_MODULES += ("handover_recovery.py", "acquisition_supervisor.py")


def control_identity(root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = set(SOURCE_PATHS) | {"acquisition_control_server.pyw"} | {"elyse_agent/" + name for name in CONTROL_MODULES}
    paths.add("data/standard_telemetry_schema.json")
    digest = hashlib.sha256()
    for path in sorted(paths):
        with open(os.path.join(root, *path.split("/")), "rb") as source:
            raw = source.read()
        name = path.encode("utf-8")
        digest.update(str(len(name)).encode("ascii") + b":" + name)
        digest.update(str(len(raw)).encode("ascii") + b":" + raw)
    return dict(runtime_protocol_version=2, session_id=uuid.uuid4().hex, build_id=digest.hexdigest())


def _execution_context(method):
    """Bind observations to the operation actually entered by the NI owner.

    A later accepted stop/close changes runtime revision. Samples emitted by
    the superseded call must not become fresh data for that newer operation.
    """
    @wraps(method)
    def call(self, *args, **kwargs):
        previous = self._context
        if previous is None:
            with self.runtime._lock:
                self._context = dict(session_id=self.runtime._identity["session_id"],
                    state_revision=self.runtime._state_revision, operation=self.runtime._operation,
                    backend_identity=id(self.backend))
        try:
            if previous is None and method.__name__ != "close":
                expected = {"general_start": "modulator.general.start", "general_stop": "modulator.general.stop",
                    "configure_counter_timing": "acq.stage.counter_timing.configure",
                    "outer_controlled_stop": "acq.outer.controlled_stop",
                    "execute_cooling_guard": "acq.timeout.cooling_trip"}.get(method.__name__)
                if method.__name__ == "execute_stage" and args:
                    expected = "acq.stage." + args[0]
                if method.__name__ == "_call" and args:
                    expected = "acq.stage." + args[0]
                if expected is not None and self._context["operation"] != expected:
                    raise ProcedureCancelled("Superseded procedure cannot enter another operation's context")
                self._assert_active_context(AcquisitionCancelled if method.__name__
                    in ("initialize", "read_snapshot") else ProcedureCancelled)
            return method(self, *args, **kwargs)
        finally:
            self._context = previous
    return call


class _ObservedBackend(object):
    def __init__(self, backend, runtime):
        self.backend, self.runtime = backend, runtime
        self._context = None
        observer = getattr(backend, "set_execution_observer", None)
        if observer is not None:
            observer(self._observe)

    def _observe(self, event):
        if type(event) is not dict or self._context is None:
            return
        value = dict(event, runtime_operation_context=copy.deepcopy(self._context))
        self.runtime.observe_execution(value)

    def _assert_active_context(self, error_type=ProcedureCancelled):
        value = dict(runtime_operation_context=self._context)
        isolated = getattr(self.backend, "isolation_snapshot", None)
        if isolated is not None:
            value["worker_generation"] = isolated().get("worker_generation")
        with self.runtime._lock:
            if not self.runtime._observation_context_current(value):
                raise error_type("Procedure superseded by a newer lifecycle request")

    def __getattr__(self, name):
        return getattr(self.backend, name)

    @_execution_context
    def _call(self, operation, method, *args, **kwargs):
        token = self.runtime.broker.begin(operation)
        error = None
        try:
            return getattr(self.backend, method)(*args, **kwargs)
        except Exception as caught:
            error = caught
            raise
        finally:
            self.runtime.broker.finish(token, error)
            if operation == "modulator.general.stop" and self.runtime.cooling.snapshot()["active"]:
                self.runtime.cooling.stop_result("" if error is None else str(error))

    @_execution_context
    def general_start(self, *args, **kwargs):
        token = self.runtime.broker.begin("modulator.general.start")
        error = None
        self.runtime._general_cooling_ready = False
        try:
            self.runtime._startup_phase = "GENERAL_POWER"
            result = self.backend.general_start(*args, **kwargs)
            self._assert_active_context()
            self.runtime._startup_phase = "COOLING_START"
            self.backend.execute_stage("cooling.start", args[0], operator_confirmed=True)
            self._assert_active_context()
            self.runtime._verify_cooling(self.backend, args[0])
            self._assert_active_context()
            self.runtime._general_cooling_ready = True
            return result
        except Exception as caught:
            error = caught
            self.runtime._startup_phase = "FAILED_LATER_STARTS_BLOCKED"
            raise
        finally:
            self.runtime.broker.finish(token, error)

    @_execution_context
    def general_stop(self, *args, **kwargs):
        self.runtime._general_cooling_ready = False
        self.runtime._startup_phase = "STOPPING"
        try:
            result = self._call("modulator.general.stop", "general_stop", *args, **kwargs)
        except Exception:
            self.runtime._startup_phase = "STOP_FAILED_LOCAL_VERIFICATION_REQUIRED"
            raise
        self.runtime._startup_phase = "GENERAL_STOP_SEQUENCE_COMPLETED"
        return result

    @_execution_context
    def execute_stage(self, operation, *args, **kwargs):
        if operation in BEAMLINE_OPERATIONS:
            if self.runtime._general_cooling_ready is not True:
                raise RuntimeError("GENERAL_AND_CONFIRMED_COOLING_REQUIRED")
            self.runtime._start_permit()
        if operation == "cooling.start":
            token, error = self.runtime.broker.begin(operation), None
            try:
                result = self.backend.execute_stage(operation, *args, **kwargs)
                self._assert_active_context()
                self.runtime._verify_cooling(self.backend, args[0])
                return result
            except Exception as caught:
                error = caught
                self.runtime._startup_phase = "COOLING_FAILED_LATER_STARTS_BLOCKED"
                raise
            finally:
                self.runtime.broker.finish(token, error)
        return self._call(operation, "execute_stage", operation, *args, **kwargs)

    def execute_impulsion(self, operation, *args, **kwargs):
        return self._call(operation, "execute_impulsion", operation, *args, **kwargs)

    def set_ht_voltage(self, *args, **kwargs):
        return self._call("ht_voltage.set", "set_ht_voltage", *args, **kwargs)

    @_execution_context
    def initialize(self, *args, **kwargs):
        return self.backend.initialize(*args, **kwargs)

    @_execution_context
    def read_snapshot(self, *args, **kwargs):
        return self.backend.read_snapshot(*args, **kwargs)

    @_execution_context
    def configure_counter_timing(self, *args, **kwargs):
        return self.backend.configure_counter_timing(*args, **kwargs)

    @_execution_context
    def configure_sync_parameters(self, *args, **kwargs):
        return self._call("counter_timing.set", "configure_sync_parameters", *args, **kwargs)

    @_execution_context
    def outer_controlled_stop(self, *args, **kwargs):
        return self.backend.outer_controlled_stop(*args, **kwargs)

    @_execution_context
    def execute_cooling_guard(self, *args, **kwargs):
        return self.backend.execute_cooling_guard(*args, **kwargs)

    @_execution_context
    def close(self):
        self.runtime.broker.interrupt_queued()
        self.runtime._general_cooling_ready = False
        return self.backend.close()


class AcquisitionControlRuntime(AcquisitionRuntime):
    def _owner_telemetry_current(self):
        if (self._backend is None or not self._backend.resource_count or self._error
                or self._state not in ("RUNNING", "EXECUTING") or self._pending is not None
                or self._shutdown_requested or self._cancel.is_set()
                or self._recovery_latched or self._marker_cleanup_uncertain):
            return False
        isolated = getattr(self._backend, "isolation_snapshot", None)
        return isolated is None or isolated().get("ownership_uncertain") is False

    def _measurement_current(self, age):
        return bool(self._owner_telemetry_current() and self._latest is not None
                    and type(age) in (int, float) and math.isfinite(age) and 0 <= age < 2)

    def _software_telemetry(self, now):
        age = None if self._software_received_at is None else max(0., now - self._software_received_at)
        return dict(software_state=copy.deepcopy(self._software_state),
                    software_state_age_seconds=age, software_state_sequence=self._software_sequence,
                    software_state_current=bool(self._software_state is not None
                        and self._owner_telemetry_current() and not self._software_error),
                    software_state_error=self._software_error)

    def try_telemetry_snapshot(self):
        """RAM-only projection. Never wait for command admission or a journal."""
        if not self._lock.acquire(False):
            return None
        try:
            now = self._clock()
            age = None if self._received_at is None else max(0, now - self._received_at)
            recovery = self._recovery_latched or self._marker_cleanup_uncertain or self._state == 'RECOVERY_REQUIRED'
            current = self._measurement_current(age)
            result = dict(self._identity, state=self._state, sequence=self._sequence,
                        state_revision=self._state_revision, error=self._error,
                        resource_count=0 if self._backend is None else self._backend.resource_count,
                        latest=copy.deepcopy(self._latest), age_seconds=age,
                        stale=not current, measurement_current=current,
                        telemetry_view_current=True,
                        telemetry_bridge_mode=((self._state == 'IDLE' and not self._error and not recovery
                            or self._cold_prior_recovery_bridge and self._state == 'RECOVERY_REQUIRED'
                            and self._recovery_latched and not self._marker_cleanup_uncertain)
                            and self._backend is None and self._operation is None
                            and self._pending is None and not self._shutdown_requested
                        ))
            result.update(self._software_telemetry(now))
            return result
        finally:
            self._lock.release()

    def initialize(self, startup_confirmed=False):
        with self._lock:
            publisher = getattr(self, "telemetry_publisher", None)
            if publisher is not None and hasattr(publisher, "assert_initialize_allowed"):
                publisher.assert_initialize_allowed()
            result = AcquisitionRuntime.initialize(self, startup_confirmed)
            self._software_state, self._software_received_at = None, None
            self._software_sequence, self._software_error = 0, ""
            # An accepted native ownership attempt permanently closes the cold
            # prior-session exception. A native fault must never fall back to VI.
            self._cold_prior_recovery_bridge = False
            return result

    def __init__(self, backend_factory, remote_enabled=False, cooling=None, handover_verifier=None,
                 cooling_polarity_verified=False, cooling_start_timeout=30.0, **kwargs):
        if type(cooling_polarity_verified) is not bool:
            raise ValueError("Exact cooling polarity verification required")
        AcquisitionRuntime.__init__(self, lambda: _ObservedBackend(backend_factory(), self), **kwargs)
        # A prior installation marker restricts NI ownership, not passive VI
        # forwarding by a fresh process that has never constructed a backend.
        # This is a boot-time RAM fact, not a PID/NI cleanup certificate. Keep
        # RECOVERY_REQUIRED and its marker unchanged; all command gates remain.
        self._cold_prior_recovery_bridge = self._state == 'RECOVERY_REQUIRED'
        self._handover_verifier = handover_verifier
        self.broker = CommandBroker(self, enabled=remote_enabled, clock=self._clock)
        self.cooling = cooling if cooling is not None else CoolingSafety(clock=self._clock)
        self.cooling_polarity_verified = cooling_polarity_verified
        self._circuits = None
        self._cooling_read_at = None
        self._watchdog_stop, self._watchdog = threading.Event(), None
        if type(cooling_start_timeout) not in (int, float) or not 2 <= cooling_start_timeout <= 120:
            raise ValueError("Cooling startup timeout must be in [2,120] seconds")
        self._cooling_start_timeout = cooling_start_timeout
        self._general_cooling_ready = False
        self._startup_phase = "NOT_STARTED"
        self._execution_progress = None
        self._software_state, self._software_received_at = None, None
        self._software_sequence, self._software_error = 0, ""

    def initialize_after_handover(self, startup_confirmed=False, electrical_off_confirmed=False,
                                  confirmation=None, operator=None):
        """Explicit local handover only; never a remote or automatic action.

        Process absence is checked by the verifier; release of external NI
        tasks and electrical OFF are separately attested by the local operator.
        An active/uncertain current native owner is never recoverable this way.
        """
        if startup_confirmed is not True or electrical_off_confirmed is not True:
            raise ValueError("Explicit local startup and electrical OFF confirmations required")
        with self._lock:
            guard, verifier = self._recovery_guard, self._handover_verifier
            if (self._state != "RECOVERY_REQUIRED" or not self._cold_prior_recovery_bridge
                    or self._backend is not None or self._pending is not None or self._operation is not None
                    or self._shutdown_requested or self._marker_cleanup_uncertain
                    or guard is None or verifier is None or guard.quiescence_checker is not verifier):
                raise RuntimeError("Local handover requires a cold prior-owner recovery state")
            publisher = getattr(self, "telemetry_publisher", None)
            if publisher is not None:
                publisher.assert_initialize_allowed()
            with verifier.local_confirmation(confirmation, operator):
                self.recover_local(electrical_off_confirmed=True)
            # Recheck the VI fence after process inventory and audit I/O. New
            # VI traffic can never be followed by construction of our backend.
            self.initialize(startup_confirmed=True)

    def acknowledge_journal_history(self, operator=None, reason=None, expected_revision=None):
        """Local metadata acknowledgment only; no lifecycle/NI side effects."""
        return self.cooling.acknowledge_journal_history(qualified_local=True,
            operator=operator, reason=reason, expected_revision=expected_revision)

    def _observation_context_current(self, value):
        context = value.get("runtime_operation_context")
        if (type(context) is not dict or self._backend is None
                or context.get("session_id") != self._identity["session_id"]
                or context.get("state_revision") != self._state_revision
                or context.get("operation") != self._operation
                or context.get("backend_identity") != id(getattr(self._backend, "backend", self._backend))
                or self._pending is not None or self._shutdown_requested or self._cancel.is_set()
                or self._recovery_latched or self._marker_cleanup_uncertain
                or self._state not in ("INITIALIZING", "RUNNING", "EXECUTING")):
            return False
        isolation = getattr(self._backend, "isolation_snapshot", None)
        if isolation is not None:
            owner = isolation()
            if (owner.get("ownership_uncertain") is not False
                    or value.get("worker_generation") != owner.get("worker_generation")):
                return False
        return True

    @staticmethod
    def _valid_execution_sample(sample):
        if (type(sample) is not dict or sample.get("source") != "python_daqmx_acquisition"
                or sample.get("simulated") is not False or type(sample.get("banks")) is not dict):
            return False
        def finite_vector(value, count):
            return (type(value) in (list, tuple) and len(value) == count and all(
                _finite_number(item) for item in value))
        for name, device, count in AI_BANKS:
            bank = sample["banks"].get(name, {})
            if (type(bank) is not dict or bank.get("kind") != "analog_input" or bank.get("device") != device
                    or not finite_vector(bank.get("values"), count)
                    or not finite_vector(bank.get("legacy_scaled_values"), count)):
                return False
        for name, device, unused_first, unused_last, count in DI_BANKS:
            bank = sample["banks"].get(name, {})
            if type(bank) is not dict:
                return False
            values = bank.get("values")
            if (bank.get("kind") != "digital_input" or bank.get("device") != device
                    or type(values) not in (list, tuple) or len(values) != count
                    or any(type(item) is not bool for item in values)):
                return False
        return True

    def _observe_software_state(self, value):
        state, previous = value.get("software_state"), self._software_state
        age = value.get("software_state_age_seconds", 0.)
        if (type(state) is not dict or set(state) != {"revision", "EPS", "DPS"}
                or type(state.get("revision")) is not int or state["revision"] <= 0
                or value.get("simulated") is not False
                or value.get("hardware_acknowledged") is not False
                or not _finite_number(age) or age < 0
                or any(type(state.get(name)) not in (list, tuple) or len(state[name]) != count
                    or any(type(item) is not bool for item in state[name])
                    for name, count in (("EPS", 77), ("DPS", 29)))):
            self._software_error = "INVALID_SOFTWARE_STATE_NOT_MEASUREMENT"
            return
        local = dict(EPS=list(state["EPS"]), DPS=list(state["DPS"]))
        if previous is not None:
            if state["revision"] < previous["source_revision"]:
                self._software_error = "SOFTWARE_STATE_REVISION_REGRESSED"
                return
            if state["revision"] == previous["source_revision"] and local != previous["local_banks"]:
                self._software_error = "SOFTWARE_REVISION_CHANGED_WITHOUT_NEW_REVISION"
                return
        self._software_sequence += 1
        self._software_state = dict(source="python_acquisition_software_memory", simulated=False,
            session_id=self._identity["session_id"], sequence=self._software_sequence,
            source_revision=state["revision"], local_banks=local,
            hardware_acknowledged=False, psp_delivery_acknowledged=False,
            source_effect=value.get("source_effect", "OWNER_OBSERVATION"))
        if type(value.get("publication")) is dict:
            self._software_state["source_publication"] = copy.deepcopy(value["publication"])
        self._software_received_at, self._software_error = self._clock() - age, ""

    def observe_execution(self, event):
        """Progress is not a measurement or proof that a driver is responsive.

        An optional qualified sample comes from the same child NI owner. Do not
        compare process-local monotonic epochs or refresh data on a heartbeat.
        """
        if type(event) is not dict:
            return
        value = copy.deepcopy(event)
        sample = value.pop("sample", None)
        sample_age = value.get("sample_age_seconds")
        with self._lock:
            current = self._observation_context_current(value)
            self._execution_progress = dict(value, observation_current=current)
            if not current:
                return
            if value.get("kind") == "SOFTWARE_STATE_NOT_MEASUREMENT":
                self._observe_software_state(value)
                return  # A software observation never refreshes measurement time.
            if sample is not None or value.get("sample_error") is not None:
                valid = (self._state == "EXECUTING" and value.get("safe_to_sample") is True
                    and value.get("sample_error") is None and self._valid_execution_sample(sample)
                    and _finite_number(sample_age) and 0 <= sample_age < 2)
                if not valid:
                    self._received_at = None
                    return
                self._sequence += 1
                self._latest = sample
                self._latest["received_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._received_at = self._clock() - sample_age

    def _verify_cooling(self, backend, cancel):
        self._startup_phase = "WAIT_CANON_SECTION_CIRCULATION"
        context = copy.deepcopy(getattr(self._backend, "_context", None))
        def observe(sample, circuits):
            with self._lock:
                if context is not None:
                    observation = dict(runtime_operation_context=context)
                    isolated = getattr(backend, "isolation_snapshot", None)
                    if isolated is not None:
                        observation["worker_generation"] = isolated().get("worker_generation")
                    if not self._observation_context_current(observation):
                        return
                self._sequence += 1
                self._latest = copy.deepcopy(sample)
                self._latest["received_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._received_at = self._cooling_read_at = self._clock()
                self._circuits = circuits
                self.cooling.observe(circuits, self._general_stop_required, observation_id=self._sequence)
        result = wait_for_cooling(backend.read_snapshot, cancel, observe,
                                  timeout=self._cooling_start_timeout, clock=self._clock)
        self._startup_phase = "COOLING_CONFIRMED"
        return result

    def _stop_qualified(self):
        backend = self._backend
        return bool(backend is not None and backend.resource_count
                    and backend.control_profile == "extended_ht_stop"
                    and getattr(backend, "ht_feedback_verified", False) is True
                    and getattr(getattr(backend, "focal_command", None), "resources_verified", False) is True
                    and self.cooling_polarity_verified)

    def _start_permit(self, general=False):
        alarm = self.cooling.snapshot()
        # An acknowledged-by-operator decision to proceed despite a historical
        # gap is NOT a claim that missing records were recovered. Keep that
        # warning and durable=false visible, but gate starts on CURRENT writer
        # health/commit readiness and active incidents, not old history alone.
        if (alarm["active"] or alarm.get("journal_storage_error", alarm["journal_error"])
                or alarm.get("journal_required") and alarm.get("journal_write_ready") is not True):
            raise RuntimeError("Start blocked by unresolved cooling alarm or journal failure")
        if not self._stop_qualified():
            raise RuntimeError("Start blocked: full HT/Chroma/cooling shutdown not commissioned")
        # General supplies the circulation cabinet. Requiring running water
        # before General itself would prevent establishing circulation.
        if not general and (self._cooling_read_at is None or self._clock() - self._cooling_read_at >= 2
                            or not self._circuits or any(item["fault"] is not False
                            or item["quality"] != "FRESH" for item in self._circuits.values())):
            raise RuntimeError("Start blocked: fresh normal Canon and Section cooling indications required")

    def dispatch_remote(self, operation, value):
        require_command(self.snapshot(), operation, value)
        if operation == "modulator.general.start":
            return self.general_start(operator_confirmed=True)
        if operation == "modulator.general.stop":
            accepted = self.general_stop(operator_confirmed=True)
            self.broker.interrupt_queued()
            return accepted
        if operation == "ht_voltage.set":
            self._start_permit()
            return self.set_ht_voltage(value, operator_confirmed=True)
        if operation == "counter_timing.set":
            self._start_permit()
            return self.set_sync_parameters(value, operator_confirmed=True)
        if operation == "cooling.start":
            if not self._stop_qualified():
                raise RuntimeError("Cooling recovery requires commissioned shutdown")
        elif (operation.endswith(".start") or operation.endswith(".reset")
              or operation in BEAMLINE_OPERATIONS):
            self._start_permit()
        return self.stage_request(operation, operator_confirmed=True)

    def general_start(self, operator_confirmed=False):
        with self._lock:
            self._start_permit(general=True)
            return AcquisitionRuntime.general_start(self, operator_confirmed)

    def _run_cooling_guard(self, latest):
        with self._lock:
            self._circuits, unused = decode_publications(runtime_publications(latest))
            self._cooling_read_at = self._clock()
            self.cooling.observe(self._circuits, self._general_stop_required, observation_id=self._sequence)
        return AcquisitionRuntime._run_cooling_guard(self, latest)

    def _tick_cooling(self):
        with self._lock:
            if self._cooling_read_at is None or self._clock() - self._cooling_read_at >= 2:
                self.cooling.observe({name: dict(fault=None, quality="UNKNOWN", causes=[])
                                     for name in ("CANON", "SECTION")}, self._general_stop_required)
            ready = self._stop_qualified() and not self._shutdown_requested and not self._stop_in_progress(self._operation)
            if self.cooling.tick(ready):
                try:
                    self.general_stop(operator_confirmed=True)
                    self.broker.interrupt_queued()
                except Exception as error:
                    self.cooling.stop_result(error=str(error))

    def _watch_cooling(self):
        while not self._watchdog_stop.wait(.1):
            try:
                self._tick_cooling()
            except Exception as error:
                with self._lock:
                    self._error = "Cooling watchdog failed: " + str(error)
                    self._state = "FAULT"
                    self.cooling.stop_result(error=self._error)

    def start(self):
        AcquisitionRuntime.start(self)
        self._watchdog = threading.Thread(target=self._watch_cooling, name="ACQ-cooling-watchdog")
        self._watchdog.daemon = True
        self._watchdog.start()

    def join(self, timeout=None):
        started = time.monotonic()
        stopped = AcquisitionRuntime.join(self, timeout)
        if stopped:
            self._watchdog_stop.set()
            if self._watchdog is not None:
                remaining = None if timeout is None else max(0, timeout - (time.monotonic() - started))
                self._watchdog.join(remaining)
                stopped = not self._watchdog.is_alive()
        return stopped

    def snapshot(self):
        with self._lock:
            result = AcquisitionRuntime.snapshot(self)
            current = self._measurement_current(result["age_seconds"])
            result.update(stale=not current, measurement_current=current)
            result.update(self._software_telemetry(self._clock()))
            result["server_variant"] = "acquisition_control_vnext"
            result["control_policy_version"] = 2
            publisher = getattr(self, "telemetry_publisher", None)
            result["telemetry_delivery"] = publisher.status() if publisher is not None else dict(enabled=False)
            result["remote_setpoints_enabled"] = self.broker.enabled
            result["stage_execution"]["remote_commands_enabled"] = self.broker.enabled
            # Internal UI/watchdog/policy reads never consume command leases.
            # Only the authenticated HTTP snapshot reply issues one.
            result["control"] = self.broker.snapshot(issue_lease=False)
            result["full_stop_commissioned"] = self._stop_qualified()
            result["general_cooling_ready"] = self._general_cooling_ready
            result["startup_phase"] = self._startup_phase
            result["execution_progress"] = copy.deepcopy(self._execution_progress)
            isolated = getattr(self._backend, "isolation_snapshot", None)
            result["native_isolation"] = isolated() if isolated is not None else dict(
                worker_state="NOT_SPAWNED" if self._backend is None else "IN_PROCESS_TEST_BACKEND",
                resource_count=0 if self._backend is None else self._backend.resource_count,
                automatic_restart=False)
            result["local_handover_available"] = bool(self._handover_verifier is not None
                and self._recovery_guard is not None
                and self._recovery_guard.quiescence_checker is self._handover_verifier
                and self._cold_prior_recovery_bridge and self._state == "RECOVERY_REQUIRED"
                and self._backend is None and self._pending is None and self._operation is None
                and not self._shutdown_requested and not self._marker_cleanup_uncertain
                and not result["recovery"].get("owns_current_marker"))
            result["cooling_permit_current"] = bool(
                self._cooling_read_at is not None and 0 <= self._clock() - self._cooling_read_at < 2
                and self._circuits and all(item.get("quality") == "FRESH"
                and item.get("fault") is False for item in self._circuits.values())
                and not self.cooling.snapshot()["active"])
            result["control"]["capabilities"] = command_capabilities(result)
            result["cooling_safety"] = self.cooling.snapshot()
            result["chroma_configuration"] = [dict(focale=row[0], xp_resource=row[1],
                moxa_host="10.20.30.51", moxa_port=index + 1, voltage_v=row[2],
                current_slew_source_value=row[3], current_a=row[4], physical_output_state="UNKNOWN")
                for index, row in enumerate(BRANCHES)]
            return result
