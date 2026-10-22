"""Read only the fixed Everest telemetry receiver. No XP, NI or PSP access."""

import json
import math
from datetime import datetime, timezone

import tango_gateway
from flask import Blueprint, current_app, jsonify, request, Response
from pathlib import Path
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS
from mutation_auth import install_mutation_auth

DEVICE = "tango://10.20.30.202:10000/elyse/acquisition/telemetry"
MAX_JSON_BYTES = 2 * 1024 * 1024
STALE_SECONDS = 2
acq_telemetry_api = Blueprint(
    "acq_telemetry_api", __name__, url_prefix="/api/elyse/acquisition/telemetry"
)
install_mutation_auth(acq_telemetry_api, protected_get_endpoints=(
    "get_telemetry", "get_cooling_safety", "get_history", "get_archive_status", "get_history_view"))


@acq_telemetry_api.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def browser_data(value):
    """Preserve integer precision in browsers; never turn unavailable into zero."""
    if type(value) is int and abs(value) > 2**53 - 1:
        return {"integer_decimal": str(value)}
    if isinstance(value, list):
        return [browser_data(item) for item in value]
    if isinstance(value, dict):
        return {key: browser_data(item) for key, item in value.items()}
    return value


def present_snapshot(raw, server_state):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("invalid telemetry attribute size")
    snapshot = json.loads(raw)
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("source") not in ("copied_labview_telemetry", "python_daqmx_acquisition")
        or snapshot.get("hardware_writes") is not False
        or snapshot.get("storage_mode") != "ram_latest"
        or not isinstance(snapshot.get("publications"), dict)
    ):
        raise ValueError("unexpected telemetry receiver contract")
    publications = snapshot["publications"]
    if set(publications) - set(BANKS):
        raise ValueError("unexpected telemetry bank")
    for bank in publications.values():
        if not isinstance(bank, dict):
            raise ValueError("invalid telemetry bank")
        age = bank.get("age_seconds")
        if type(age) not in (int, float) or not math.isfinite(age) or age < 0:
            raise ValueError("invalid telemetry age")
        error = bank.get("error")
        if (
            not isinstance(error, dict)
            or type(error.get("status")) is not bool
            or type(error.get("code")) is not int
            or not isinstance(error.get("source"), str)
        ):
            raise ValueError("invalid bank read error")
        bank["stale"] = bank.get("stale") is not False or age >= STALE_SECONDS
        bank["data"] = browser_data(bank.get("data"))
    # Strict JSON: a corrupt receiver must not send NaN/Infinity to the browser.
    json.dumps(snapshot, allow_nan=False)
    missing = [name for name in BANKS if name not in publications]
    stale = [name for name, bank in publications.items() if bank["stale"]]
    errors = [
        name
        for name, bank in publications.items()
        if bank["error"]["status"] or bank["error"]["code"] != 0
    ]
    unavailable = [name for name in errors if snapshot.get("source") == "python_daqmx_acquisition"
                   and publications[name]["producer_kind"] == "python_acquisition"
                   and publications[name]["error"]["code"] == -80001
                   and publications[name]["data"] is None]
    read_errors = [name for name in errors if name not in unavailable]
    quality = (
        "RECEIVER_NOT_READY"
        if server_state != "ON"
        else "WAITING"
        if not publications
        else "READ_ERROR"
        if read_errors
        else "STALE"
        if stale
        else "INCOMPLETE"
        if missing or unavailable
        else "FRESH"
    )
    return dict(
        schema_version=1,
        execution_allowed=False,
        hardware_writes=False,
        source_host="10.20.30.10",
        device="elyse/acquisition/telemetry",
        server_state=server_state,
        observed_utc=datetime.now(timezone.utc).isoformat(),
        stale_after_seconds=STALE_SECONDS,
        expected_banks=list(BANKS),
        quality=quality,
        missing_banks=missing,
        stale_banks=stale,
        error_banks=errors,
        unavailable_banks=unavailable,
        source=snapshot["source"],
        snapshot=snapshot,
        cooling_safety=snapshot.get("cooling_safety"),
    )


@acq_telemetry_api.get("")
def get_telemetry():
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(1500)
        state, attribute = proxy.read_attributes(["State", "telemetry_json"])
        if state.has_failed or attribute.has_failed:
            raise ValueError("Tango telemetry attribute unavailable")
        return jsonify(present_snapshot(attribute.value, str(state.value)))
    except Exception as error:
        # No fallback to PSP, card reads or a command-capable device.
        current_app.logger.warning(
            "ACQ telemetry read unavailable: %s", type(error).__name__
        )
        return jsonify(
            schema_version=1,
            execution_allowed=False,
            hardware_writes=False,
            quality="UNAVAILABLE",
            error="Récepteur de télémétrie Tango indisponible.",
        ), 503


@acq_telemetry_api.get("/archive")
def get_archive_status():
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(2000)
        attr = proxy.read_attribute('archive_status_json')
        if attr.has_failed:
            raise ValueError('Archive status unavailable')
        value = json.loads(attr.value)
        if request.args.get('include_imports') == '1':
            try:
                summary = json.loads(proxy.command_inout('ArchiveSummary'))
                value['imports'] = summary['imports']
                value['frames'] = summary['frames']
            except Exception:
                value['imports_status'] = 'UNKNOWN'
        return jsonify(value)
    except Exception:
        return jsonify(available=False, error='Archive status unavailable'), 503


@acq_telemetry_api.get('/history-view')
def get_history_view():
    return Response(Path(__file__).with_name('telemetry_history.html').read_text(encoding='utf-8'),
                    mimetype='text/html')


@acq_telemetry_api.get("/history")
def get_history():
    allowed = {'bank', 'index', 'start', 'end', 'limit', 'cursor_time', 'cursor_uid'}
    try:
        if set(request.args) - allowed or any(len(request.args.getlist(k)) != 1 for k in request.args):
            raise ValueError('Invalid history query')
        query = dict(request.args)
        query['index'] = int(query['index'])
        query['limit'] = int(query.get('limit', 1000))
        if query.get('bank') not in BANKS or not 0 <= query['index'] <= 8191 or not 1 <= query['limit'] <= 5000:
            raise ValueError('Invalid history channel or limit')
        for key in ('start', 'end'):
            parsed = datetime.fromisoformat(query[key].replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                raise ValueError('History timestamps require timezone')
    except (ValueError, KeyError):
        return jsonify(error='Known bank, index, timezone-qualified start/end and limit 1..5000 required'), 400
    try:
        proxy = tango_gateway.create_device_proxy(DEVICE)
        proxy.set_timeout_millis(4000)
        raw = proxy.command_inout('ReadHistory', json.dumps(query))
        return jsonify(browser_data(json.loads(raw)))
    except Exception:
        return jsonify(error='PostgreSQL history unavailable; live telemetry is separate'), 503


@acq_telemetry_api.get("/cooling")
def get_cooling_safety():
    """Explicit source, never a fallback from Python control to LabVIEW data."""
    source = current_app.config.get("ELYSE_COOLING_SOURCE", "labview")
    try:
        if source == "labview":
            proxy = tango_gateway.create_device_proxy(DEVICE)
            proxy.set_timeout_millis(1500)
            state, attr = proxy.read_attributes(["State", "telemetry_json"])
            if state.has_failed or attr.has_failed or str(state.value) != "ON":
                raise ValueError("Telemetry receiver not ready")
            body = present_snapshot(attr.value, str(state.value))
            safety = body["cooling_safety"]
            if body["source"] == "python_daqmx_acquisition":
                source = "xp_control"
        elif source == "xp_runtime":
            proxy = tango_gateway.create_device_proxy(
                "tango://10.20.30.202:10000/elyse/acquisition/runtime")
            proxy.set_timeout_millis(1500)
            attr = proxy.read_attribute("runtime_json")
            if attr.has_failed or not isinstance(attr.value, str) or len(attr.value) > MAX_JSON_BYTES:
                raise ValueError("Runtime attribute unavailable")
            bridge = json.loads(attr.value)
            if bridge.get("source") != "xp_python_acquisition_runtime" or bridge.get("bridge_stale") is not False:
                raise ValueError("Authenticated runtime bridge is stale")
            runtime = bridge.get("runtime", {})
            if (runtime.get("auto_initialize") is not False
                    or runtime.get("remote_initialization_enabled") is not False
                    or runtime.get("remote_setpoints_enabled") is not False):
                raise ValueError("Runtime contract incompatible")
            safety = runtime.get("cooling_safety")
        else:
            raise ValueError("Unknown cooling source")
        if not isinstance(safety, dict) or safety.get("schema_version") != 1:
            raise ValueError("Cooling alarm service not installed on selected source")
        if source == "labview" and safety.get("automatic_stop_available") is not False:
            raise ValueError("Read-only LabVIEW receiver cannot claim shutdown authority")
        if (safety.get("timeout_seconds") != 120 or type(safety.get("active")) is not bool
                or type(safety.get("automatic_stop_available")) is not bool
                or safety.get("stop_state") not in ("NONE", "REQUESTED", "UNAVAILABLE", "INTERRUPTED", "FAILED", "COMPLETED")
                or not isinstance(safety.get("circuits"), list)
                or len(safety["circuits"]) > 2):
            raise ValueError("Invalid cooling alarm schema")
        seen = set()
        for incident in safety["circuits"]:
            if not isinstance(incident, dict) or incident.get("circuit") not in ("CANON", "SECTION"):
                raise ValueError("Invalid cooling circuit")
            if incident["circuit"] in seen:
                raise ValueError("Duplicate cooling incident")
            seen.add(incident["circuit"])
            for key in ("started_utc", "deadline_utc"):
                if datetime.fromisoformat(incident[key]).utcoffset() is None:
                    raise ValueError("Timezone required for cooling alarm")
            remaining = incident.get("remaining_seconds")
            if type(remaining) not in (int, float) or not math.isfinite(remaining) or not 0 <= remaining <= 120:
                raise ValueError("Invalid cooling countdown")
        if safety["active"] != bool(safety["circuits"]):
            raise ValueError("Inconsistent cooling alarm state")
        # This route is observation-only even when XP independently owns a
        # locally commissioned stop policy. It never submits that stop.
        return jsonify(schema_version=1, execution_allowed=False, hardware_writes=False,
                       source=source, cooling_safety=safety)
    except Exception as error:
        current_app.logger.warning("Cooling alarm source unavailable: %s", type(error).__name__)
        return jsonify(schema_version=1, execution_allowed=False, hardware_writes=False,
                       source=source, error="Service d’alarme refroidissement indisponible."), 503
