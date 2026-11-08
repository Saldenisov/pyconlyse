"""Bounded, non-actuating receiver for copied Acquisition publications.

No NI, PSP, serial, simulation-output or procedure calls belong in this module.
Producer claims are retained as claims, not certified physical measurements.
Compatible with Python 3.4; only standard-library dependencies.
"""
from __future__ import division

import copy
import datetime
import json
import math
import threading
import time

from .errors import CommandError
from .telemetry_relay import TelemetryOutbox


# Saved main VI runtime publication families. This is NOT a channel/pin map.
PUBLICATIONS = (
    "C1NI6071E", "C2NI6071E", "C3_IN_DIO96", "C4_IN_DIO96",
    "C5_IN_DIO96", "EPS", "EPC", "VTA",
)
# Additional *observed software publications*, not measured AO voltages.
# Opt-in keeps the already commissioned eight-family reader contract unchanged.
ALL_PUBLICATIONS = PUBLICATIONS + (
    "C3_OUT_DIO96", "C4_OUT_DIO96", "C5_OUT_DIO96",
    "C6NI6703", "C7NI6703", "C8NI6703", "C9NI6703",
    "C1011NI6602", "DPS", "VDM-A", "VAM-A",
)
TELEMETRY_COMMANDS = ("ingest_labview_telemetry", "get_labview_telemetry")
READ_ONLY_COMMANDS = ("ping", "get_status", "get_capabilities") + TELEMETRY_COMMANDS


def _check_json(value, depth=0, budget=None):
    if budget is None:
        budget = [8192]
    budget[0] -= 1
    if depth > 12 or budget[0] < 0:
        raise CommandError("telemetry payload exceeds structural limit")
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str) and len(value) > 4096:
            raise CommandError("telemetry string exceeds limit")
        return
    if isinstance(value, (int, float)):
        try:
            finite = math.isfinite(value)
        except (OverflowError, ValueError):
            finite = False
        if not finite:
            raise CommandError("telemetry numbers must be finite; encode unavailable values as null")
        return
    if isinstance(value, list):
        for item in value:
            _check_json(item, depth + 1, budget)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 128:
                raise CommandError("telemetry object keys must be short strings")
            _check_json(item, depth + 1, budget)
        return
    raise CommandError("telemetry payload must contain JSON values only")


def validate_packet(params, publications=PUBLICATIONS, session_id=None, structural_limit=8192):
    expected = set(("session_id", "publication", "sequence", "source_seconds_1904",
                    "producer_kind", "data", "error"))
    if type(params) is not dict or set(params) not in (expected, expected | set(("source_site",))):
        raise CommandError("invalid telemetry packet fields")
    if not isinstance(params["session_id"], str) or not 1 <= len(params["session_id"]) <= 128:
        raise CommandError("invalid producer session")
    if session_id is not None and params["session_id"] != session_id:
        raise CommandError("telemetry producer session does not match receiver")
    publication = params["publication"]
    if not isinstance(publication, str) or publication not in publications:
        raise CommandError("unknown Acquisition publication")
    if type(params["sequence"]) is not int or not 0 <= params["sequence"] <= 9007199254740991:
        raise CommandError("telemetry sequence must be an integer in 0..2^53-1")
    stamp = params["source_seconds_1904"]
    try:
        finite_stamp = type(stamp) in (int, float) and math.isfinite(stamp)
    except (OverflowError, ValueError):
        finite_stamp = False
    if not finite_stamp or stamp < 0:
        raise CommandError("source_seconds_1904 must be finite and nonnegative")
    if params["producer_kind"] not in ("fixture", "copied_acquisition", "python_acquisition"):
        raise CommandError("Unknown telemetry producer kind")
    error = params["error"]
    if type(error) is not dict or set(error) != set(("status", "code", "source")):
        raise CommandError("error must contain LabVIEW status, code and source")
    if type(error["status"]) is not bool or type(error["code"]) is not int:
        raise CommandError("error status/code must be Boolean/integer")
    if not isinstance(error["source"], str):
        raise CommandError("error source must be a string")
    if "source_site" in params and (not isinstance(params["source_site"], str)
                                  or not 1 <= len(params["source_site"]) <= 128):
        raise CommandError("invalid source publication site")
    if type(structural_limit) is not int or not 1 <= structural_limit <= 32768:
        raise CommandError("invalid telemetry structural limit")
    _check_json(params, budget=[structural_limit])
    encoded = json.dumps(params, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("utf-8")) > 262144:
        raise CommandError("telemetry publication exceeds 256 KiB")
    return encoded


class LabviewTelemetryStore(object):
    def __init__(self, session_id, stale_after_seconds=2.0, clock=None, outbox=None,
                 include_all_publications=False):
        if not isinstance(session_id, str) or not 1 <= len(session_id) <= 128:
            raise ValueError("telemetry session id must contain 1..128 characters")
        if not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0:
            raise ValueError("telemetry stale interval must be finite and positive")
        self.session_id = session_id
        self.stale_after_seconds = float(stale_after_seconds)
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._latest = {}
        self.publications = ALL_PUBLICATIONS if include_all_publications else PUBLICATIONS
        self.outbox = outbox if outbox is not None else TelemetryOutbox(clock=self._clock)

    def ingest(self, params, peer):
        # The existing listener may serve remote readers. Only local LabVIEW
        # may publish. This is locality checking, not producer authentication.
        if not isinstance(peer, str) or peer.rsplit(":", 1)[0] != "127.0.0.1":
            raise CommandError("LabVIEW telemetry ingestion requires IPv4 loopback")
        encoded = validate_packet(params, self.publications, self.session_id)
        publication = params["publication"]
        sequence = params["sequence"]
        with self._lock:
            previous = self._latest.get(publication)
            if previous and sequence <= previous["packet"]["sequence"]:
                if sequence == previous["packet"]["sequence"] and encoded == previous["encoded"]:
                    # Retransmission must not make stale data look fresh.
                    return {"accepted": True, "duplicate": True, "publication": publication,
                            "sequence": sequence, "hardware_writes": False}
                raise CommandError("telemetry sequence regressed or was reused with different data")
            received_utc = datetime.datetime.utcnow().isoformat() + "Z"
            try:
                self.outbox.enqueue(encoded, received_utc)
            except ValueError as error:
                raise CommandError(str(error))
            self._latest[publication] = {
                "packet": copy.deepcopy(params), "encoded": encoded,
                "received_monotonic": self._clock(),
                "received_utc": received_utc,
            }
        return {"accepted": True, "duplicate": False, "publication": publication,
                "sequence": sequence, "hardware_writes": False}

    def snapshot(self):
        with self._lock:
            now = self._clock()
            publications = {}
            for name, entry in self._latest.items():
                packet = copy.deepcopy(entry["packet"])
                age = max(0.0, now - entry["received_monotonic"])
                packet["received_utc"] = entry["received_utc"]
                packet["age_seconds"] = age
                packet["stale"] = age >= self.stale_after_seconds
                packet["producer_reports_error"] = packet["error"]["status"]
                publications[name] = packet
            return {
                "source": "labview_telemetry", "session_id": self.session_id,
                "producer_identity_authenticated": False,
                "physical_measurements_verified": False,
                "hardware_writes": False, "input_task_creation": False,
                "atomic_across_publications": False,
                "stale_after_seconds": self.stale_after_seconds,
                "missing_publications": sorted(set(self.publications) - set(publications)),
                "publications": publications,
                "fifo": self.outbox.status(),
            }
