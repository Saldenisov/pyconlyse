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

from .acquisition_runtime import AcquisitionRuntime
from .acquisition_remote import CommandBroker
from .cooling_safety import CoolingSafety, decode_publications, runtime_publications
from .chroma_focal_stop import BRANCHES
from .runtime_identity import SOURCE_PATHS
from .control_policy import require_command, command_capabilities
from .cooling_startup import wait_for_cooling

CONTROL_MODULES = ("acquisition_remote.py", "acquisition_control_runtime.py",
                   "acquisition_control_gui.py", "cooling_safety.py",
                   "acquisition_driver_diagnostics.py", "control_policy.py", "cooling_startup.py")
CONTROL_MODULES += ("native_telemetry.py", "shared_state.py", "labview_telemetry.py",
                    "telemetry_relay.py", "protocol.py", "supervision_wire.py", "errors.py",
                    "dual_mode_telemetry.py", "shared_state_receiver.py")


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


class _ObservedBackend(object):
    def __init__(self, backend, runtime):
        self.backend, self.runtime = backend, runtime

    def __getattr__(self, name):
        return getattr(self.backend, name)

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

    def general_start(self, *args, **kwargs):
        token = self.runtime.broker.begin("modulator.general.start")
        error = None
        self.runtime._general_cooling_ready = False
        try:
            self.runtime._startup_phase = "GENERAL_POWER"
            result = self.backend.general_start(*args, **kwargs)
            self.runtime._startup_phase = "COOLING_START"
            self.backend.execute_stage("cooling.start", args[0], operator_confirmed=True)
            self.runtime._verify_cooling(self.backend, args[0])
            self.runtime._general_cooling_ready = True
            return result
        except Exception as caught:
            error = caught
            self.runtime._startup_phase = "FAILED_LATER_STARTS_BLOCKED"
            raise
        finally:
            self.runtime.broker.finish(token, error)

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

    def execute_stage(self, operation, *args, **kwargs):
        if operation == "cooling.start":
            token, error = self.runtime.broker.begin(operation), None
            try:
                result = self.backend.execute_stage(operation, *args, **kwargs)
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

    def close(self):
        self.runtime.broker.interrupt_queued()
        self.runtime._general_cooling_ready = False
        return self.backend.close()


class AcquisitionControlRuntime(AcquisitionRuntime):
    def initialize(self, startup_confirmed=False):
        with self._lock:
            publisher = getattr(self, "telemetry_publisher", None)
            if publisher is not None and hasattr(publisher, "assert_initialize_allowed"):
                publisher.assert_initialize_allowed()
            return AcquisitionRuntime.initialize(self, startup_confirmed)

    def __init__(self, backend_factory, remote_enabled=False, cooling=None,
                 cooling_polarity_verified=False, cooling_start_timeout=30.0, **kwargs):
        if type(cooling_polarity_verified) is not bool:
            raise ValueError("Exact cooling polarity verification required")
        AcquisitionRuntime.__init__(self, lambda: _ObservedBackend(backend_factory(), self), **kwargs)
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

    def _verify_cooling(self, backend, cancel):
        self._startup_phase = "WAIT_CANON_SECTION_CIRCULATION"
        def observe(sample, circuits):
            with self._lock:
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
        if alarm["active"] or alarm["journal_error"]:
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
        require_command(self.snapshot(), operation)
        if operation == "modulator.general.start":
            return self.general_start(operator_confirmed=True)
        if operation == "modulator.general.stop":
            accepted = self.general_stop(operator_confirmed=True)
            self.broker.interrupt_queued()
            return accepted
        if operation == "ht_voltage.set":
            self._start_permit()
            return self.set_ht_voltage(value, operator_confirmed=True)
        if operation == "cooling.start":
            if not self._stop_qualified():
                raise RuntimeError("Cooling recovery requires commissioned shutdown")
        elif operation.endswith(".start") or operation.endswith(".reset"):
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
        stopped = AcquisitionRuntime.join(self, timeout)
        if stopped:
            self._watchdog_stop.set()
            if self._watchdog is not None:
                self._watchdog.join(.5)
        return stopped

    def snapshot(self):
        with self._lock:
            result = AcquisitionRuntime.snapshot(self)
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
