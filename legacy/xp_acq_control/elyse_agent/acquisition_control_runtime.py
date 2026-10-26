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
from .cooling_safety import CoolingSafety, RECOVERY_SECONDS, decode_publications, runtime_publications
from .chroma_focal_stop import BRANCHES
from .runtime_identity import SOURCE_PATHS
from .control_policy import require_command, command_capabilities, BEAMLINE_OPERATIONS
from .cooling_startup import wait_for_cooling
from .card_observation import card_inputs_current, generation_vector, selected_generations, source_age
from .hardware_plan import AI_BANKS, DI_BANKS
from .acquisition_procedures import ProcedureCancelled
from .acquisition_backend import AcquisitionCancelled
from .supervised_test import SUPERVISED_OPERATIONS, supervised_enabled
from .command_protocol import validate_circulation_confirmation


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
CONTROL_MODULES += ("parallel_initialization.py",)
CONTROL_MODULES += ("supervised_test.py",)
CONTROL_MODULES += ("card_service.py", "card_process_owner.py", "card_observation.py", "native_process_spawn.py",
                    "orchestrator_backend.py")
CONTROL_MODULES += ("federation_wire.py", "orchestrator_publisher.py", "synchronization_profiles.py",
                    "supervision_cards.py", "supervision_imaq.py", "supervision_service.py",
                    "supervision_runtime.py", "supervision_gui.py")


def control_identity(root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = set(SOURCE_PATHS) | {"acquisition_control_server.pyw", "supervision_control_server.pyw"} | {"elyse_agent/" + name for name in CONTROL_MODULES}
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
        self.runtime._invalidate_cooling_readiness()
        try:
            if self.runtime._supervised_admission("modulator.general.start"):
                with self.runtime._lock:
                    self.runtime._start_permit(general=True,
                        observed_at=self.runtime._supervised_operation_observation_at)
            self.runtime._startup_phase = "GENERAL_POWER"
            result = self.backend.general_start(*args, **kwargs)
            self._assert_active_context()
            if self.runtime._supervised_admission("modulator.general.start"):
                self.runtime._begin_supervised_general_epoch()
                self.runtime._startup_phase = "WAIT_OPERATOR_WATER"
                return result
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
        self.runtime._invalidate_cooling_readiness()
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
        if self.runtime._supervised_admission(operation):
            with self.runtime._lock:
                self.runtime._require_startup_complete()
                self.runtime._require_recovery_clear()
                self.runtime._require_supervised_owner_inputs(operation, fresh=False)
                if not operation.endswith(".stop"):
                    if operation == "cooling.start":
                        self.runtime._require_current_owner_inputs(
                            self.runtime._supervised_operation_observation_at, operation)
                        if not self.runtime._supervised_general_current():
                            raise RuntimeError("GENERAL_REQUIRED_BEFORE_OPERATOR_WATER")
                    else:
                        self.runtime._start_permit(operation=operation,
                            observed_at=self.runtime._supervised_operation_observation_at)
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
        self.runtime._invalidate_cooling_readiness()
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
                    and card_inputs_current(self._latest, getattr(self._backend, "card_processes", None))
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
            isolated = getattr(self._backend, "isolation_snapshot", None)
            native = isolated() if isolated is not None else None
            result = dict(self._identity, state=self._state, sequence=self._sequence,
                        state_revision=self._state_revision, error=self._error,
                        resource_count=0 if self._backend is None else self._backend.resource_count,
                        latest=copy.deepcopy(self._latest), age_seconds=age,
                        stale=not current, measurement_current=current,
                        fault_diagnostic_measurement=self._fault_diagnostic_snapshot(now, native),
                        telemetry_view_current=True,
                        telemetry_bridge_mode=((self._state == 'IDLE' and not self._error and not recovery
                            or self._cold_prior_recovery_bridge and self._state == 'RECOVERY_REQUIRED'
                            and self._recovery_latched and not self._marker_cleanup_uncertain)
                            and self._backend is None and self._operation is None
                            and self._pending is None and not self._shutdown_requested
                        ))
            if native is not None:
                result["native_isolation"] = native
            result["card_processes"] = copy.deepcopy(getattr(self._backend, "card_processes", None))
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
            self._invalidate_cooling_readiness()
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
        self.cooling.bind_experiment_session(self._identity["session_id"])
        self._cooling_ht_active = False
        self._cooling_ht_owner = None
        self._cooling_ht_reason = "HT_NOT_APPLIED_IN_CURRENT_EXPERIMENT"
        self.cooling_polarity_verified = cooling_polarity_verified
        self._circuits = None
        self._cooling_read_at = None
        self._watchdog_stop, self._watchdog = threading.Event(), None
        if type(cooling_start_timeout) not in (int, float) or not 2 <= cooling_start_timeout <= 120:
            raise ValueError("Cooling startup timeout must be in [2,120] seconds")
        self._cooling_start_timeout = cooling_start_timeout
        self._general_cooling_ready = False
        self._supervised_general_owner = None
        self._supervised_general_generation = None
        self._supervised_general_card_vector = None
        self._supervised_cooling_since = None
        self._supervised_cooling_samples = 0
        self._startup_phase = "NOT_STARTED"
        self._execution_progress = None
        self._software_state, self._software_received_at = None, None
        self._software_sequence, self._software_error = 0, ""

    def _cooling_experiment_active(self, latest=None, received_at=None):
        """Latch actual qualified HT exposure, not General or an HT setpoint.

        Uses accepted NI input memory only. Missing/stale inputs, uncertain
        ownership and native faults cannot clear an already active exposure.
        """
        backend = self._backend
        if backend is None or not getattr(backend, "resource_count", 0):
            return self._cooling_ht_active
        isolated = getattr(backend, "isolation_snapshot", None)
        native = isolated() if isolated is not None else {}
        owner = (id(backend), native.get("worker_generation"))
        if (getattr(backend, "startup_complete", False) is not True
                or native.get("ownership_uncertain") is not False
                or not owner[1] or getattr(backend, "ht_feedback_verified", False) is not True):
            return self._cooling_ht_active
        if self._cooling_ht_active and self._cooling_ht_owner != owner:
            return True  # Another/unknown owner is not proof of zero HT.
        age = None if received_at is None else self._clock() - received_at
        tolerance = getattr(backend, "ht_zero_tolerance_kv", None)
        if (not _finite_number(age) or not 0 <= age < 2
                or not _finite_number(tolerance) or not 0 <= tolerance < 8
                or type(latest) is not dict or latest.get("source") != "python_daqmx_acquisition"
                or latest.get("simulated") is not False):
            return self._cooling_ht_active
        if not card_inputs_current(latest, getattr(backend, "card_processes", None)):
            return self._cooling_ht_active
        banks = latest.get("banks", {})
        volts = banks.get("C2_NI6071E_AI", {}).get("legacy_scaled_values")
        contacts = banks.get("C4_DIO96_DI", {}).get("values")
        if (not isinstance(volts, (list, tuple)) or len(volts) != 64 or not _finite_number(volts[7])
                or not isinstance(contacts, (list, tuple)) or len(contacts) != 64
                or any(type(item) is not bool for item in contacts)):
            return self._cooling_ht_active
        if not self._cooling_ht_active:
            if self._general_stop_required and contacts[48] is False and volts[7] > tolerance:
                self._cooling_ht_active, self._cooling_ht_owner = True, owner
                self._cooling_ht_reason = "FRESH_QUALIFIED_HT_APPLIED"
        elif (contacts[48] is True and abs(volts[7]) <= tolerance and not self._pulse_stop_required):
            self._cooling_ht_active = False
            self._cooling_ht_reason = "FRESH_QUALIFIED_HT_ZERO_SUPPLY_OFF_PULSES_STOPPED"
        return self._cooling_ht_active

    def _observe_cooling_inputs(self, circuits, latest, received_at):
        self.cooling.observe(circuits, self._cooling_experiment_active(latest, received_at),
                             observation_id=self._sequence)

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

    def counter_memory_part(self):
        """Current C10 software command memory, independently of other cards."""
        with self._lock:
            backend = self._backend
            if (backend is None or not getattr(backend, "startup_complete", False)
                    or self._pending in ("initialize", "close", "counter_timing")
                    or self._operation in ("acq.stage.counter_timing.configure", "acq.stage.counter_timing.set")
                    or self._shutdown_requested):
                return None
            cards = getattr(backend, "card_processes", None) or {}
            card = cards.get("cards", {}).get("10", {})
            age = card.get("sample_age_seconds")
            transport = cards.get("transport_age_seconds", 0.)
            if (card.get("state") != "READY" or card.get("input_current") is not True
                    or card.get("native", {}).get("ownership_uncertain") is not False
                    or card.get("unresolved_request") or not _finite_number(age)
                    or not _finite_number(transport) or not 0 <= age + transport < 2
                    or card.get("native", {}).get("worker_generation") !=
                       getattr(backend, "_counter_config_generation", None)
                    or getattr(backend, "_counter_configuration_uncertain", ())):
                return None
            ticks = getattr(backend, "commanded_counter_ticks", {})
            try:
                values = [ticks[i][key] / 20. for i in range(8) for key in ("low_ticks", "high_ticks")]
            except (KeyError, TypeError):
                return None
            return dict(values=values, source_age_seconds=age + transport,
                        source="last_successful_counter_command_memory", selector=-1, pending_selector=False)

    def _observation_context_current(self, value):
        context = value.get("runtime_operation_context")
        if (type(context) is not dict or self._backend is None
                or context.get("session_id") != self._identity["session_id"]
                or context.get("state_revision") != self._state_revision
                or context.get("operation") != self._operation
                or context.get("backend_identity") != id(getattr(self._backend, "backend", self._backend))
                or self._pending is not None or self._shutdown_requested or self._cancel.is_set()
                or self._recovery_latched or self._marker_cleanup_uncertain
                or (self._state not in ("INITIALIZING", "RUNNING", "EXECUTING")
                    and not (self._state == "FAULT" and self._fault_diagnostic_read_in_progress
                             and self._operation is None))):
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
            if self._state == "FAULT":
                return  # Only the returned diagnostic read can attest a measurement.
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
                # Feed the same accepted owner image to the RAM cooling policy
                # immediately during long procedures. Never enter the source
                # cooling guard or issue NI operations from this observer.
                previous_read_at = self._cooling_read_at
                self._circuits, unused = decode_publications(runtime_publications(sample))
                self._cooling_read_at = self._received_at
                self._observe_cooling_inputs(self._circuits, sample, self._received_at)
                self._observe_supervised_cooling(previous_read_at)

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
                self._received_at = self._cooling_read_at = self._clock() - source_age(sample)
                self._circuits = circuits
                self._observe_cooling_inputs(circuits, sample, self._received_at)
        result = wait_for_cooling(backend.read_snapshot, cancel, observe,
                                  timeout=self._cooling_start_timeout, clock=self._clock)
        self._startup_phase = "COOLING_CONFIRMED"
        if self._supervised_general_current():
            self._general_cooling_ready = True
        return result

    def _invalidate_cooling_readiness(self, end_epoch=True):
        self._general_cooling_ready = False
        self._supervised_cooling_since = None
        self._supervised_cooling_samples = 0
        if end_epoch:
            self._supervised_general_owner = None
            self._supervised_general_generation = None
            self._supervised_general_card_vector = None

    def _begin_supervised_general_epoch(self):
        self._invalidate_cooling_readiness()
        self._supervised_general_owner = self._backend
        isolation = getattr(self._backend, "isolation_snapshot", None)
        self._supervised_general_generation = (isolation().get("worker_generation")
                                               if isolation is not None else None)
        self._supervised_general_card_vector = generation_vector(getattr(self._backend, "card_processes", None))

    def _supervised_general_current(self):
        if (not self._supervised_admission("modulator.general.start")
                or self._supervised_general_owner is not self._backend
                or not self._general_stop_required or not self._backend.resource_count):
            return False
        cards = getattr(self._backend, "card_processes", None)
        if cards is not None and (generation_vector(cards) is None
                or generation_vector(cards) != self._supervised_general_card_vector):
            return False
        isolation = getattr(self._backend, "isolation_snapshot", None)
        if isolation is not None:
            owner = isolation()
            return (owner.get("ownership_uncertain") is False
                    and owner.get("worker_generation") == self._supervised_general_generation)
        return True

    def _observe_supervised_cooling(self, previous_read_at):
        if not supervised_enabled(self._backend):
            return
        now = self._clock()
        normal = (self._supervised_general_current() and self._owner_telemetry_current()
            and self._latest is not None and self._latest.get("source") == "python_daqmx_acquisition"
            and self._latest.get("simulated") is False and set(self._circuits or {}) == {"CANON", "SECTION"}
            and all(item.get("quality") == "FRESH" and item.get("fault") is False
                    for item in self._circuits.values()))
        if not normal:
            self._invalidate_cooling_readiness(end_epoch=False)
            return
        if previous_read_at is None or not 0 <= now - previous_read_at < 2:
            self._invalidate_cooling_readiness(end_epoch=False)
        if self._supervised_cooling_since is None:
            self._supervised_cooling_since = now
        self._supervised_cooling_samples += 1
        if self._supervised_cooling_samples >= 2 and now - self._supervised_cooling_since >= RECOVERY_SECONDS:
            self._general_cooling_ready = True
            self._startup_phase = "COOLING_CONFIRMED"

    def _procedure_fault(self, error):
        self._invalidate_cooling_readiness()
        return AcquisitionRuntime._procedure_fault(self, error)

    def deinitialize(self, electrical_off_confirmed=False):
        with self._lock:
            result = AcquisitionRuntime.deinitialize(self, electrical_off_confirmed)
            self._invalidate_cooling_readiness()
            if electrical_off_confirmed is True:
                self._end_cooling_experiment_locally()
            return result

    def request_shutdown(self, electrical_off_confirmed=False):
        with self._lock:
            result = AcquisitionRuntime.request_shutdown(self, electrical_off_confirmed)
            self._invalidate_cooling_readiness()
            if electrical_off_confirmed is True:
                self._end_cooling_experiment_locally()
            return result

    def _end_cooling_experiment_locally(self):
        self._cooling_ht_active, self._cooling_ht_owner = False, None
        self._cooling_ht_reason = "LOCAL_ELECTRICAL_OFF_ATTESTED"
        self.cooling.observe({name: dict(fault=None, quality="UNKNOWN", causes=[])
            for name in ("CANON", "SECTION")}, False, observation_id=self._sequence)

    def general_stop(self, operator_confirmed=False):
        with self._lock:
            if self._supervised_admission("modulator.general.stop"):
                self._require_recovery_clear()
                self._require_supervised_owner_inputs("modulator.general.stop", fresh=False)
            result = AcquisitionRuntime.general_stop(self, operator_confirmed)
            self._invalidate_cooling_readiness()
            return result

    def stage_request(self, operation, operator_confirmed=False, new_value=True):
        with self._lock:
            if self._supervised_admission(operation) and new_value is True:
                if operation == "cooling.start":
                    if not self._supervised_general_current():
                        raise RuntimeError("GENERAL_REQUIRED_BEFORE_OPERATOR_WATER")
                elif operation.endswith(".start") or operation.endswith(".reset"):
                    self._start_permit(operation=operation)
            return AcquisitionRuntime.stage_request(self, operation, operator_confirmed, new_value)

    def _stop_qualified(self):
        backend = self._backend
        return bool(backend is not None and backend.resource_count
                    and backend.control_profile == "extended_ht_stop"
                    and getattr(backend, "ht_feedback_verified", False) is True
                    and getattr(getattr(backend, "focal_command", None), "resources_verified", False) is True
                    and self.cooling_polarity_verified)

    def _start_permit(self, general=False, operation=None, observed_at=None):
        alarm = self.cooling.snapshot()
        # An acknowledged-by-operator decision to proceed despite a historical
        # gap is NOT a claim that missing records were recovered. Keep that
        # warning and durable=false visible, but gate starts on CURRENT writer
        # health/commit readiness and active incidents, not old history alone.
        if (alarm["active"] or alarm.get("journal_storage_error", alarm["journal_error"])
                or alarm.get("journal_required") and alarm.get("journal_write_ready") is not True):
            raise RuntimeError("Start blocked by unresolved cooling alarm or journal failure")
        operation = "modulator.general.start" if general else operation
        supervised = self._supervised_admission(operation)
        if not self._stop_qualified() and not supervised:
            raise RuntimeError("Start blocked: full HT/Chroma/cooling shutdown not commissioned")
        if supervised:
            self._require_startup_complete()
            self._require_recovery_clear()
            self._require_supervised_owner_inputs(operation, fresh=False)
            if self._error or self._cancel.is_set():
                raise RuntimeError("SUPERVISED_TEST_REQUIRES_CURRENT_OWNER_INPUTS")
            self._require_current_owner_inputs(
                self._received_at if observed_at is None else observed_at, operation)
            if not general and (not self._supervised_general_current() or not self._general_cooling_ready):
                raise RuntimeError("GENERAL_AND_CONFIRMED_COOLING_REQUIRED")
        # General supplies the circulation cabinet. Requiring running water
        # before General itself would prevent establishing circulation.
        if not general and (self._cooling_read_at is None or self._clock() - self._cooling_read_at >= 2
                            or not self._circuits or any(item["fault"] is not False
                            or item["quality"] != "FRESH" for item in self._circuits.values())):
            raise RuntimeError("Start blocked: fresh normal Canon and Section cooling indications required")

    def dispatch_remote(self, operation, value):
        if operation == "cooling.confirm_circulation":
            with self._lock:
                confirmation = validate_circulation_confirmation(value)
                require_command(self.snapshot(), operation, confirmation)
                self.cooling.confirm_circulation(confirmation["incident_ids"],
                                                 operator="authenticated_remote_operator")
                return dict(completed_without_hardware=True,
                            confirmed_incident_ids=list(confirmation["incident_ids"]))
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
            if not self._stop_qualified() and not self._supervised_admission(operation):
                raise RuntimeError("Cooling recovery requires commissioned shutdown")
        elif (operation.endswith(".start") or operation.endswith(".reset")
              or operation in BEAMLINE_OPERATIONS):
            if self._supervised_admission(operation):
                self._start_permit(operation=operation)
            else:
                self._start_permit()
        return self.stage_request(operation, operator_confirmed=True)

    def general_start(self, operator_confirmed=False):
        with self._lock:
            self._start_permit(general=True)
            return AcquisitionRuntime.general_start(self, operator_confirmed)

    def _run_cooling_guard(self, latest):
        with self._lock:
            previous_read_at = self._cooling_read_at
            self._circuits, unused = decode_publications(runtime_publications(latest))
            self._cooling_read_at = self._clock()
            self._observe_cooling_inputs(self._circuits, latest, self._cooling_read_at)
            self._observe_supervised_cooling(previous_read_at)
        return AcquisitionRuntime._run_cooling_guard(self, latest)

    def _observe_fault_diagnostic(self, latest):
        self._circuits, unused = decode_publications(runtime_publications(latest))
        self._cooling_read_at = self._clock()
        self._observe_cooling_inputs(self._circuits, latest, self._cooling_read_at)
        self._invalidate_cooling_readiness()

    def _tick_cooling(self):
        with self._lock:
            if self._cooling_read_at is None or self._clock() - self._cooling_read_at >= 2:
                if supervised_enabled(self._backend):
                    self._invalidate_cooling_readiness(end_epoch=False)
                self.cooling.observe({name: dict(fault=None, quality="UNKNOWN", causes=[])
                                     for name in ("CANON", "SECTION")}, self._cooling_ht_active)
            ready = ((self._stop_qualified() or self._supervised_admission("modulator.general.stop"))
                     and not self._shutdown_requested and not self._stop_in_progress(self._operation))
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
            result["pending_operation"] = self._pending
            result["shutdown_requested"] = self._shutdown_requested
            result["cancellation_requested"] = self._cancel.is_set()
            result["stage_execution"]["remote_commands_enabled"] = self.broker.enabled
            # Internal UI/watchdog/policy reads never consume command leases.
            # Only the authenticated HTTP snapshot reply issues one.
            result["control"] = self.broker.snapshot(issue_lease=False)
            result["full_stop_commissioned"] = self._stop_qualified()
            result["operator_supervised_test"] = supervised_enabled(self._backend)
            result["operator_test_cold_attested"] = bool(
                self._backend is not None and getattr(self._backend, "operator_test_cold_attested", False) is True)
            result["operator_cold_water_only"] = bool(result["operator_test_cold_attested"]
                and getattr(self._backend, "operator_cold_water_only", False) is True)
            result["operator_test_general_epoch_current"] = self._supervised_general_current()
            result["operator_test_admission"] = dict(
                enabled=result["operator_supervised_test"],
                cold_attested=result["operator_test_cold_attested"],
                permitted_operations=sorted(SUPERVISED_OPERATIONS) if result["operator_supervised_test"] else [],
                interpretation="Operator test permission only; physical commissioning facts remain separate")
            if (result["operator_supervised_test"] and (self._cooling_read_at is None
                    or not 0 <= self._clock() - self._cooling_read_at < 2)):
                self._invalidate_cooling_readiness(end_epoch=False)
            result["general_cooling_ready"] = self._general_cooling_ready
            result["startup_phase"] = self._startup_phase
            result["execution_progress"] = copy.deepcopy(self._execution_progress)
            result["initialization_cards"] = copy.deepcopy(getattr(self._backend, "initialization_cards", None))
            result["card_processes"] = copy.deepcopy(getattr(self._backend, "card_processes", None))
            result["startup_complete"] = getattr(self._backend, "startup_complete", None)
            isolated = getattr(self._backend, "isolation_snapshot", None)
            result["native_isolation"] = isolated() if isolated is not None else dict(
                worker_state="NOT_SPAWNED" if self._backend is None else "IN_PROCESS_TEST_BACKEND",
                resource_count=0 if self._backend is None else self._backend.resource_count,
                ownership_uncertain=False,
                automatic_restart=False)
            if self._state == "FAULT":
                # Bind publication proof to this same native phase capture;
                # an idle/read transition cannot produce mismatched fields.
                sample_now = (self._clock() if self._received_at is None or result["age_seconds"] is None
                              else self._received_at + result["age_seconds"])
                result["fault_diagnostic_measurement"] = self._fault_diagnostic_snapshot(
                    sample_now, result["native_isolation"])
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
            result["cooling_safety"] = self.cooling.snapshot()
            result["cooling_safety"]["experiment_scope"] = dict(active=self._cooling_ht_active,
                kind="QUALIFIED_HT_EXPOSURE", reason=self._cooling_ht_reason,
                physical_off_confirmed=False)
            result["control"]["capabilities"] = command_capabilities(result)
            result["chroma_configuration"] = [dict(focale=row[0], xp_resource=row[1],
                moxa_host="10.20.30.51", moxa_port=index + 1, voltage_v=row[2],
                current_slew_source_value=row[3], current_a=row[4], physical_output_state="UNKNOWN")
                for index, row in enumerate(BRANCHES)]
            return result
