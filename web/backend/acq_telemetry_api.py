"""Read only the fixed Everest telemetry receiver. No XP, NI or PSP access."""

import json
import math
from datetime import datetime, timezone

import tango_gateway
from flask import Blueprint, current_app, jsonify
from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS
from mutation_auth import install_mutation_auth

DEVICE = "tango://10.20.30.202:10000/elyse/acquisition/telemetry"
MAX_JSON_BYTES = 2 * 1024 * 1024
STALE_SECONDS = 2
acq_telemetry_api = Blueprint(
    "acq_telemetry_api", __name__, url_prefix="/api/elyse/acquisition/telemetry"
)
install_mutation_auth(acq_telemetry_api, protected_get_endpoints=("get_telemetry",))


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
        or snapshot.get("source") != "copied_labview_telemetry"
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
    quality = (
        "RECEIVER_NOT_READY"
        if server_state != "ON"
        else "WAITING"
        if not publications
        else "READ_ERROR"
        if errors
        else "STALE"
        if stale
        else "INCOMPLETE"
        if missing
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
        snapshot=snapshot,
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
