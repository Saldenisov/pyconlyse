"""Bounded, authenticated replay API for the existing ELYSE web control tab."""

import json
import math
import sqlite3
from pathlib import Path
from threading import Lock

import elyse_supervision_service as service
from elyse_supervision_business import BusinessBlocked, BusinessConflict, SupervisionBusiness
from elyse_acq_transport import configured_acq
from flask import Blueprint, current_app, jsonify, request
from mutation_auth import install_mutation_auth

elyse_supervision_api = Blueprint(
    "elyse_supervision_api", __name__, url_prefix="/api/elyse/supervision"
)
install_mutation_auth(elyse_supervision_api, protected_get_endpoints=("get_snapshot", "get_business", "get_business_intent_trace"))
MAX_REPLAY_BYTES = 65536
_business_lock = Lock()


@elyse_supervision_api.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def unavailable(error):
    current_app.logger.error("SuperVision reconstruction unavailable: %s", error)
    return jsonify(
        error="Reconstruction data unavailable", execution_allowed=False
    ), 503


@elyse_supervision_api.get("")
def get_snapshot():
    try:
        return jsonify(service.snapshot())
    except (OSError, ImportError, ValueError, KeyError) as error:
        return unavailable(error)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)

    def finite(item):
        if isinstance(item, float):
            if not math.isfinite(item):
                raise ValueError("Non-finite numeric input")
        elif isinstance(item, list):
            for part in item:
                finite(part)
        elif isinstance(item, dict):
            for part in item.values():
                finite(part)

    finite(value)
    return value


@elyse_supervision_api.post("/replay")
def post_replay():
    if request.mimetype != "application/json":
        return jsonify(error="application/json required", execution_allowed=False), 415
    raw = request.stream.read(MAX_REPLAY_BYTES + 1)
    if len(raw) > MAX_REPLAY_BYTES:
        return jsonify(
            error="Replay body exceeds 65536 bytes", execution_allowed=False
        ), 413
    try:
        return jsonify(service.replay(strict_json(raw)))
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        return jsonify(error=str(error), execution_allowed=False), 400
    except (OSError, ImportError) as error:
        return unavailable(error)


def business():
    # App-scoped injection keeps test/simulation ACQ isolated from the live server.
    with _business_lock:
        if "elyse_supervision_business" not in current_app.extensions:
            path = current_app.config.get(
                "ELYSE_SUPERVISION_STATE_DB",
                str(Path(current_app.instance_path) / "elyse_supervision.sqlite3"),
            )
            current_app.extensions["elyse_supervision_business"] = SupervisionBusiness(path, configured_acq(current_app.config))
        return current_app.extensions["elyse_supervision_business"]


def business_body():
    if request.mimetype != "application/json":
        raise ValueError("application/json required")
    raw = request.stream.read(MAX_REPLAY_BYTES + 1)
    if len(raw) > MAX_REPLAY_BYTES:
        raise ValueError("Business body exceeds 65536 bytes")
    return strict_json(raw)


def business_error(error, status):
    return jsonify(schema_version=1, execution_allowed=False,
                   physical_status="NOT_EXECUTED", error=str(error)), status


@elyse_supervision_api.get("/business")
def get_business():
    try:
        return jsonify(business().snapshot())
    except (OSError, ImportError, ValueError, sqlite3.Error) as error:
        return unavailable(error)


@elyse_supervision_api.post("/business/intents")
def stage_business_intent():
    try:
        item = business().stage(business_body())
        return jsonify(schema_version=1, execution_allowed=False,
                       physical_status="NOT_EXECUTED", intent=item)
    except BusinessConflict as error:
        return business_error(error, 409)
    except (ValueError, TypeError, RecursionError) as error:
        return business_error(error, 400)
    except (OSError, ImportError, sqlite3.Error) as error:
        return unavailable(error)


@elyse_supervision_api.post("/business/intents/<intent_id>/submit")
def submit_business_intent(intent_id):
    try:
        data = service.exact(business_body(), ("expected_revision",))
        item = business().submit(intent_id, data["expected_revision"])
        return jsonify(schema_version=1, execution_allowed=False,
                       physical_status="NOT_EXECUTED", intent=item)
    except BusinessBlocked as error:
        return business_error(error, 409)
    except KeyError as error:
        return business_error(error, 404)
    except (ValueError, TypeError, RecursionError) as error:
        return business_error(error, 400)
    except (OSError, ImportError, sqlite3.Error) as error:
        return unavailable(error)


@elyse_supervision_api.get("/business/intents/<intent_id>/trace")
def get_business_intent_trace(intent_id):
    try:
        return jsonify(business().intent_trace(intent_id))
    except KeyError as error:
        return business_error(error, 404)
    except (OSError, ImportError, ValueError, sqlite3.Error) as error:
        return unavailable(error)
