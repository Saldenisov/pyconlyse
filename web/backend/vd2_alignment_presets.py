"""Append-only Alignment return points in the application state SQLite DB.

No Tango imports, commands, lifecycle construction or automatic restoration.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import uuid

DEVICE = "ELYSE/pdu/iTest"
CHANNELS = ("T1-1", "T1-2", "H1", "V1", "Dip1", "Dip2", "Bcd1", "Bcd2")
KINDS = {"manual_best", "search_best", "before_search", "before_restore"}
BEST_KINDS = {"manual_best", "search_best"}


def device_name(value):
    if not isinstance(value, str) or value.lower() != DEVICE.lower():
        raise ValueError("Only the configured VD2 iTest device can be saved")
    return DEVICE


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Finite numeric currents are required")
    return float(value)


def validate_channels(values, *, complete=False):
    if not isinstance(values, list) or len(values) != 8:
        raise ValueError("Exactly eight named currents are required")
    result = []
    for name, channel in zip(CHANNELS, values):
        if not isinstance(channel, dict) or channel.get("name") != name:
            raise ValueError("Saved channel order/names do not match VD2")
        slot = channel.get("id")
        if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
            raise ValueError("Invalid iTest channel ID")
        item = {"id": slot, "name": name, "value": number(channel.get("value"))}
        if complete:
            item.update({key: number(channel.get(key)) for key in ("measured", "min", "max")})
            if item["min"] >= item["max"] or not item["min"] <= item["value"] <= item["max"]:
                raise ValueError(f"{name} current exceeds its native limits")
            if channel.get("state") != 1 or isinstance(channel.get("state"), bool):
                raise ValueError(f"{name} output is not ON; settings were not saved")
            if abs(item["measured"] - item["value"]) > 0.01:
                raise ValueError(f"{name} current has not settled; settings were not saved")
            item["state"] = 1
        result.append(item)
    if len({item["id"] for item in result}) != 8:
        raise ValueError("iTest channel IDs must be unique")
    return result


def validate_intent(payload):
    allowed = {"device", "kind", "expected", "context", "quality", "parent_id", "operation_id"}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ValueError("Invalid Alignment snapshot fields")
    device = device_name(payload.get("device"))
    kind = payload.get("kind")
    if kind not in KINDS:
        raise ValueError("Invalid Alignment snapshot kind")
    op = payload.get("operation_id")
    if not isinstance(op, str) or len(op) > 64:
        raise ValueError("An operation UUID is required")
    try:
        uuid.UUID(op)
    except (ValueError, AttributeError) as exc:
        raise ValueError("An operation UUID is required") from exc
    parent = payload.get("parent_id")
    if parent is not None and (not isinstance(parent, str) or len(parent) > 64):
        raise ValueError("Invalid parent snapshot")
    if kind in {"search_best", "before_restore"} and not parent:
        raise ValueError("A source/return-point snapshot is required")
    context = payload.get("context", {})
    if not isinstance(context, dict) or len(json.dumps(context, allow_nan=False)) > 16000:
        raise ValueError("Snapshot context must be a compact JSON object")
    quality = payload.get("quality")
    if quality is not None:
        if not isinstance(quality, dict) or set(quality) != {"mean", "sd", "n"}:
            raise ValueError("Quality requires mean, SD and sample count")
        quality = {"mean": number(quality["mean"]), "sd": number(quality["sd"]), "n": quality["n"]}
        if quality["sd"] < 0 or isinstance(quality["n"], bool) or not isinstance(quality["n"], int) or quality["n"] < 3:
            raise ValueError("Quality requires at least three samples and nonnegative SD")
    if kind == "search_best" and quality is None:
        raise ValueError("Completed search statistics are required")
    return {"device": device, "kind": kind, "operation_id": op, "parent_id": parent,
            "expected": validate_channels(payload.get("expected")), "context": context, "quality": quality}


def intent_hash(intent):
    return hashlib.sha256(json.dumps(intent, sort_keys=True, allow_nan=False).encode()).hexdigest()


class SnapshotConflict(ValueError):
    pass


class AlignmentSnapshots:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def _connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=10)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS vd2_alignment_snapshots (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    device TEXT NOT NULL, kind TEXT NOT NULL, operation_id TEXT UNIQUE NOT NULL,
                    request_hash TEXT NOT NULL, snapshot_json TEXT NOT NULL)""")
                connection.execute("CREATE INDEX IF NOT EXISTS vd2_alignment_by_device ON vd2_alignment_snapshots(device,seq)")
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _existing(connection, intent):
        row = connection.execute("SELECT request_hash,snapshot_json FROM vd2_alignment_snapshots WHERE operation_id=?",
                                 (intent["operation_id"],)).fetchone()
        if row and row[0] != intent_hash(intent):
            raise SnapshotConflict("Operation ID already belongs to different settings")
        return json.loads(row[1]) if row else None

    @staticmethod
    def _parent(connection, intent):
        if not intent["parent_id"]:
            return
        row = connection.execute("SELECT device,kind FROM vd2_alignment_snapshots WHERE id=?", (intent["parent_id"],)).fetchone()
        if not row or row[0] != intent["device"]:
            raise ValueError("Source snapshot is missing or belongs to another device")
        if intent["kind"] == "search_best" and row[1] != "before_search":
            raise ValueError("Search best must refer to its before-search return point")

    def preflight(self, intent):
        with self._connection() as connection:
            existing = self._existing(connection, intent)
            self._parent(connection, intent)
            return existing

    def capture(self, intent, channels):
        channels = validate_channels(channels, complete=True)
        for expected, actual in zip(intent["expected"], channels):
            if expected["id"] != actual["id"] or abs(expected["value"] - actual["value"]) > 0.0005:
                raise SnapshotConflict("iTest currents changed after review; no snapshot saved")
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._existing(connection, intent)
            if existing:
                return existing
            self._parent(connection, intent)
            snapshot = {"id": uuid.uuid4().hex, "device": intent["device"], "kind": intent["kind"],
                        "created_at": datetime.now(timezone.utc).isoformat(), "channels": channels,
                        "parent_id": intent["parent_id"], "context": intent["context"], "quality": intent["quality"]}
            connection.execute("INSERT INTO vd2_alignment_snapshots(id,device,kind,operation_id,request_hash,snapshot_json) VALUES(?,?,?,?,?,?)",
                               (snapshot["id"], snapshot["device"], snapshot["kind"], intent["operation_id"], intent_hash(intent),
                                json.dumps(snapshot, allow_nan=False)))
            return snapshot

    def history(self, device):
        device = device_name(device)
        with self._connection() as connection:
            def latest(kinds):
                placeholders = ",".join("?" for _ in kinds)
                row = connection.execute(f"SELECT snapshot_json FROM vd2_alignment_snapshots WHERE device=? AND kind IN ({placeholders}) ORDER BY seq DESC LIMIT 1",
                                         (device, *kinds)).fetchone()
                return json.loads(row[0]) if row else None
            best = latest(("manual_best", "search_best"))
            previous = latest(("before_search",))
            before_restore = latest(("before_restore",))
            rows = connection.execute("SELECT snapshot_json FROM vd2_alignment_snapshots WHERE device=? ORDER BY seq DESC LIMIT 20", (device,)).fetchall()
            return {"best": best, "previous": previous, "before_restore": before_restore,
                    "recommended": best or previous, "history": [json.loads(row[0]) for row in rows]}
