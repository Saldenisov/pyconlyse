from __future__ import print_function

import collections
import hashlib
import json
import threading

from . import __version__
from .errors import AgentError, CommandError


class CommandRouter(object):
    COMMANDS = (
        "ping",
        "initialize",
        "get_status",
        "get_capabilities",
        "get_channel_summary",
        "discover_hardware",
        "describe_legacy_tasks",
        "get_snapshot",
        "get_psp_catalog",
        "get_psp_snapshot",
        "set_simulation_scenario",
        "advance_simulation",
        "set_simulated_digital_output",
        "set_simulated_analog_output",
        "set_simulated_counter_output",
        "reset_simulated_outputs",
    )

    def __init__(self, backend, state, registry, audit, cache_size=256):
        self.backend = backend
        self.state = state
        self.registry = registry
        self.audit = audit
        self.cache_size = int(cache_size)
        self._lock = threading.RLock()
        self._cache = collections.OrderedDict()
        self.supervision = None
        self.labview_telemetry = None

    @staticmethod
    def _validate_request(request):
        allowed = set(("id", "command", "params"))
        unknown = set(request) - allowed
        if unknown:
            raise CommandError("unknown request keys: {0}".format(", ".join(sorted(unknown))))
        request_id = request.get("id")
        command = request.get("command")
        params = request.get("params", {})
        if not isinstance(request_id, str) or not request_id.strip():
            raise CommandError("id must be a non-empty string")
        if not isinstance(command, str) or not command.strip():
            raise CommandError("command must be a non-empty string")
        if not isinstance(params, dict):
            raise CommandError("params must be an object")
        return request_id, command, params

    @staticmethod
    def _fingerprint(command, params):
        payload = json.dumps([command, params], sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def dispatch(self, request, peer=None):
        request_id = None
        command = None
        try:
            request_id, command, params = self._validate_request(request)
            if self.labview_telemetry is not None:
                from .labview_telemetry import READ_ONLY_COMMANDS, TELEMETRY_COMMANDS
                if command not in READ_ONLY_COMMANDS:
                    raise CommandError("telemetry-only mode blocks hardware, PSP and simulation commands")
                if command in TELEMETRY_COMMANDS:
                    # Always check peer/session and read current data. The
                    # legacy request-id cache must not mask freshness or ACLs.
                    self.state.count_request()
                    if command == "ingest_labview_telemetry":
                        result = self.labview_telemetry.ingest(params, peer)
                    else:
                        self._require_no_params(command, params)
                        result = self.labview_telemetry.snapshot()
                    return {"id": request_id, "ok": True, "result": result}
            if command == "supervision":
                if self.supervision is None:
                    raise CommandError("Supervision is not enabled in this agent")
                # Authenticate every request, before the legacy volatile cache.
                # Durable intent deduplication belongs to the shared runtime.
                self.state.count_request()
                result = self.supervision.dispatch(params)
                self.audit.write("supervision_rpc", request_id=request_id, peer=peer,
                                 status=result["status"])
                return {"id": request_id, "ok": True, "result": result}
            fingerprint = self._fingerprint(command, params)
            with self._lock:
                cached = self._cache.get(request_id)
                if cached:
                    if cached[0] != fingerprint:
                        raise CommandError("request id was reused with different content")
                    return cached[1]
            self.state.count_request()
            result = self._execute(command, params)
            response = {"id": request_id, "ok": True, "result": result}
            with self._lock:
                self._cache[request_id] = (fingerprint, response)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
            self.audit.write("command_succeeded", request_id=request_id, command=command, peer=peer)
            return response
        except Exception as error:
            error_code = error.code if isinstance(error, AgentError) else "internal_error"
            response = {
                "id": request_id,
                "ok": False,
                "error": {"code": error_code, "message": str(error)},
            }
            self.audit.write(
                "command_failed",
                request_id=request_id,
                command=command,
                peer=peer,
                error_code=error_code,
                error_message=str(error),
            )
            return response

    def _execute(self, command, params):
        if self.supervision and command in ("set_simulated_digital_output", "set_simulated_analog_output",
                                           "set_simulated_counter_output", "reset_simulated_outputs"):
            raise CommandError("Named procedures own outputs; unsigned raw simulation writes are disabled")
        if command == "ping":
            self._require_no_params(command, params)
            return {"reply": "pong", "version": __version__}
        if command == "initialize":
            self._require_no_params(command, params)
            return self.backend.initialize()
        if command == "get_status":
            self._require_no_params(command, params)
            result = self.state.snapshot()
            if self.supervision:
                result["supervision"] = self.supervision.runtime.read_state()
            return result
        if command == "get_capabilities":
            self._require_no_params(command, params)
            if self.labview_telemetry is not None:
                from .labview_telemetry import READ_ONLY_COMMANDS, PUBLICATIONS
                return {
                    "commands": list(READ_ONLY_COMMANDS), "hardware_writes": False,
                    "input_task_creation": False, "simulation": False,
                    "telemetry_ingest_peer": "127.0.0.1", "publications": list(PUBLICATIONS),
                    "protocol": "4-byte big-endian length + UTF-8 JSON", "protocol_version": 1,
                    "telemetry_only": True,
                }
            return {
                "commands": list(self.COMMANDS) + (["supervision"] if self.supervision else []),
                "input_task_creation": False,
                "hardware_writes": False,
                "simulated_output_mutation": not bool(self.supervision),
                "named_procedure_simulation": bool(self.supervision),
                "named_setpoint_simulation": bool(self.supervision and self.supervision.runtime.simulate_setpoints),
                "lifecycle_simulation": bool(self.supervision and self.supervision.runtime.simulate_lifecycle),
                "protocol": "4-byte big-endian length + UTF-8 JSON",
                "protocol_version": 1,
                "simulation_scenarios": ["idle", "beam_ready", "fault"],
                "psp_supervision_compatible": callable(
                    getattr(self.backend, "get_psp_snapshot", None)
                ),
                "psp_payload_format": "channel:value:source_timestamp",
                "supervision_protocol": "signed_agent_rpc_v1" if self.supervision else None,
                "supervision_shared_state": bool(self.supervision),
            }
        if command == "get_channel_summary":
            self._require_no_params(command, params)
            return self.registry.summary()
        if command == "discover_hardware":
            self._require_no_params(command, params)
            result = self.backend.discover()
            self.state.record_discovery(result)
            return result
        if command == "describe_legacy_tasks":
            self._require_no_params(command, params)
            return self.backend.describe_legacy_tasks()
        if command == "get_snapshot":
            self._require_no_params(command, params)
            return self.backend.get_snapshot()
        if command == "get_psp_catalog":
            self._require_no_params(command, params)
            if not callable(getattr(self.backend, "get_psp_catalog", None)):
                raise CommandError("PSP catalog is unavailable in this backend mode")
            return self.backend.get_psp_catalog()
        if command == "get_psp_snapshot":
            self._require_no_params(command, params)
            if not callable(getattr(self.backend, "get_psp_snapshot", None)):
                raise CommandError("PSP snapshot is unavailable in this backend mode")
            return self.backend.get_psp_snapshot()
        if command == "set_simulation_scenario":
            self._require_exact_params(command, params, ("name",))
            return self.backend.set_scenario(params["name"])
        if command == "advance_simulation":
            self._require_exact_params(command, params, ("seconds",))
            if isinstance(params["seconds"], bool):
                raise CommandError("seconds must be numeric")
            return self.backend.advance(params["seconds"])
        if command == "set_simulated_digital_output":
            self._require_exact_params(command, params, ("task", "index", "value"))
            return self.backend.set_simulated_digital_output(
                params["task"], params["index"], params["value"]
            )
        if command == "set_simulated_analog_output":
            self._require_exact_params(command, params, ("task", "index", "value_volts"))
            return self.backend.set_simulated_analog_output(
                params["task"], params["index"], params["value_volts"]
            )
        if command == "set_simulated_counter_output":
            self._require_exact_params(
                command, params, ("counter", "delay_seconds", "width_seconds", "enabled")
            )
            return self.backend.set_simulated_counter_output(
                params["counter"],
                params["delay_seconds"],
                params["width_seconds"],
                params["enabled"],
            )
        if command == "reset_simulated_outputs":
            self._require_no_params(command, params)
            return self.backend.reset_simulated_outputs()
        raise CommandError("unknown command: {0}".format(command))

    @staticmethod
    def _require_no_params(command, params):
        if params:
            raise CommandError("command {0} accepts no parameters".format(command))

    @staticmethod
    def _require_exact_params(command, params, expected):
        if set(params) != set(expected):
            raise CommandError(
                "command {0} requires exactly: {1}".format(command, ", ".join(expected))
            )

    def close(self):
        if self.supervision:
            self.supervision.close()
