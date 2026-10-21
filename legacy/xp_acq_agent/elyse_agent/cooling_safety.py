"""Cooling alarm/countdown policy, not a replacement for NI/PLC interlocks.

Python 3.4 stdlib. Polarity follows the saved Fluides indications, NOT the
separate Acquisition flow-trip predicate. Automatic control needs explicit
commissioning of that polarity and the existing full HT shutdown adapter.
"""
import copy
import datetime
import json
import math
import os
import sqlite3
import threading
import time

TIMEOUT_SECONDS = 120.0
RECOVERY_SECONDS = 2.0
CIRCUITS = {"CANON": (("C3_IN_DIO96", 0, True, "220V"),
                       ("C3_IN_DIO96", 1, False, "controller_fault"),
                       ("C3_IN_DIO96", 4, False, "pressure"),
                       ("C4_IN_DIO96", 19, True, "flow")),
            "SECTION": (("C3_IN_DIO96", 6, True, "220V"),
                         ("C3_IN_DIO96", 7, False, "controller_fault"),
                         ("C3_IN_DIO96", 10, False, "pressure"),
                         ("C4_IN_DIO96", 38, True, "flow"))}


def utc(seconds):
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).isoformat()


def _bit(publications, name, index):
    record = publications.get(name, {})
    age, error = record.get("age_seconds"), record.get("error", {})
    values = record.get("data")
    size = {"C3_IN_DIO96": 56, "C4_IN_DIO96": 64, "EPS": 77}[name]
    if (record.get("stale") is not False or type(age) not in (int, float)
            or not math.isfinite(age) or not 0 <= age < 2
            or error.get("status") is not False or type(error.get("code")) is not int or error.get("code") != 0
            or type(values) is not list or len(values) != size
            or any(type(value) is not bool for value in values)):
        return None
    return values[index]


def decode_publications(publications):
    """A stale/failed indication can neither assert health nor clear an alarm."""
    result = {}
    for name, signals in CIRCUITS.items():
        causes, unknown = [], False
        for bank, index, fault_level, label in signals:
            value = _bit(publications, bank, index)
            if value is None:
                unknown = True
            elif value is fault_level:
                causes.append(dict(signal=label, bank=bank, index=index, raw=value))
        result[name] = dict(fault=True if causes else None if unknown else False,
                            quality="UNKNOWN" if unknown else "FRESH", causes=causes)
    return result, _bit(publications, "EPS", 8)


def runtime_publications(latest):
    """Adapt only successful owner-thread reads, not cached HTTP responses."""
    records = {}
    for runtime_name, bank in (("C3_DIO96_DI", "C3_IN_DIO96"),
                               ("C4_DIO96_DI", "C4_IN_DIO96")):
        values = latest.get("banks", {}).get(runtime_name, {}).get("values")
        records[bank] = dict(data=values, stale=False, age_seconds=0,
                             error=dict(status=False, code=0))
    return records


class AlarmJournal(object):
    """Durable discrete events/state only; never records telemetry samples."""
    def __init__(self, path, namespace):
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent):
            os.makedirs(parent)
        self.lock = threading.RLock()
        self.namespace = namespace
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS cooling_state (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS cooling_events (id INTEGER PRIMARY KEY, name TEXT, payload TEXT NOT NULL)")
        self.db.commit()

    def load(self):
        with self.lock:
            row = self.db.execute("SELECT payload FROM cooling_state WHERE name=?", (self.namespace,)).fetchone()
            return json.loads(row[0]) if row else None

    def append(self, state, event):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO cooling_state VALUES (?,?)",
                            (self.namespace, json.dumps(state, allow_nan=False)))
            self.db.execute("INSERT INTO cooling_events(name,payload) VALUES (?,?)",
                            (self.namespace, json.dumps(event, allow_nan=False)))

    def events(self):
        with self.lock:
            rows = self.db.execute("SELECT payload FROM cooling_events WHERE name=? ORDER BY id DESC LIMIT 100",
                                   (self.namespace,)).fetchall()
            return [json.loads(row[0]) for row in reversed(rows)]

    def close(self):
        with self.lock:
            self.db.close()


class CoolingSafety(object):
    @classmethod
    def with_journal(cls, path, namespace, **kwargs):
        journal = None
        try:
            journal = AlarmJournal(path, namespace)
            return cls(journal=journal, **kwargs)
        except Exception as error:
            if journal is not None:
                journal.close()
            # An explicit storage alarm, not a healthy/durable fallback. The
            # running countdown must not depend on disk availability.
            result = cls(**kwargs)
            result.journal_error = "Alarm journal unavailable: " + str(error)
            return result

    def __init__(self, clock=None, wall_clock=None, journal=None):
        self.clock, self.wall = clock or time.monotonic, wall_clock or time.time
        self.journal = journal
        self.lock = threading.RLock()
        self.incidents, self.recovering, self.events = {}, {}, []
        self.stop_state, self.stop_error = "NONE", ""
        self.journal_error = ""
        self.automatic_stop_available = False
        self.machine_active = None
        self.quality = "UNKNOWN"
        if journal is not None:
            saved = journal.load()
            if saved:
                self.incidents = saved["incidents"]
                self.stop_state = saved["stop_state"]
                self.stop_error = saved.get("stop_error", "")
                for item in self.incidents.values():
                    remaining = item["deadline_epoch"] - self.wall()
                    # Backward wall-clock steps never grant a new grace period.
                    if remaining > TIMEOUT_SECONDS:
                        remaining = 0
                    item["deadline_monotonic"] = self.clock() + max(0, remaining)
                self.events = journal.events()
                # A previous process's queued request is not a completed stop.
                if self.stop_state == "REQUESTED":
                    self.stop_state = "INTERRUPTED"

    def _event(self, kind, circuit=None, **extra):
        event = dict(kind=kind, circuit=circuit, observed_utc=utc(self.wall()), **extra)
        self.events = (self.events + [event])[-100:]
        if self.journal is not None:
            try:
                self.journal.append(dict(incidents=self.incidents, stop_state=self.stop_state,
                                         stop_error=self.stop_error), event)
                self.journal_error = ""
            except Exception as error:
                # Storage failure must not cancel the deadline or hide the alarm.
                self.journal_error = str(error)

    def observe(self, circuits, machine_active, observation_id=None):
        with self.lock:
            self.machine_active = machine_active
            self.quality = "FRESH" if all(c.get("quality") == "FRESH" for c in circuits.values()) else "UNKNOWN"
            for name, reading in circuits.items():
                item = self.incidents.get(name)
                if reading["fault"] is True:
                    self.recovering.pop(name, None)
                    if item is None and machine_active is True:
                        now, wall = self.clock(), self.wall()
                        self.incidents[name] = dict(circuit=name, started_utc=utc(wall),
                            deadline_utc=utc(wall + TIMEOUT_SECONDS), deadline_epoch=wall + TIMEOUT_SECONDS,
                            deadline_monotonic=now + TIMEOUT_SECONDS, causes=copy.deepcopy(reading["causes"]))
                        self._event("CIRCULATION_LOST", name, causes=reading["causes"])
                elif item is not None and reading["fault"] is False and reading["quality"] == "FRESH":
                    previous = self.recovering.get(name)
                    if previous is None:
                        self.recovering[name] = (self.clock(), observation_id)
                    elif (self.clock() - previous[0] >= RECOVERY_SECONDS
                          and observation_id is not None and observation_id != previous[1]
                          and self.stop_state in ("NONE", "COMPLETED")):
                        del self.incidents[name]
                        self.recovering.pop(name, None)
                        if not self.incidents:
                            self.stop_state, self.stop_error = "NONE", ""
                        self._event("CIRCULATION_RESTORED", name)
                else:
                    self.recovering.pop(name, None)

    def tick(self, automatic_stop_available=False):
        """Return one stop request, never a hardware command or process exit."""
        with self.lock:
            self.automatic_stop_available = automatic_stop_available is True
            due = any(self.clock() >= item["deadline_monotonic"] for item in self.incidents.values())
            if due and self.stop_state in ("NONE", "UNAVAILABLE", "INTERRUPTED"):
                if self.automatic_stop_available:
                    self.stop_state = "REQUESTED"
                    self._event("SHUTDOWN_REQUESTED")
                    return True
                if self.stop_state == "NONE":
                    self.stop_state = "UNAVAILABLE"
                    self._event("SHUTDOWN_UNAVAILABLE")
            return False

    def stop_result(self, error=""):
        with self.lock:
            self.stop_state = "FAILED" if error else "COMPLETED"
            self.stop_error = str(error)
            self._event("SHUTDOWN_FAILED" if error else "SHUTDOWN_COMPLETED", error=str(error))

    def snapshot(self):
        with self.lock:
            items = []
            for item in self.incidents.values():
                public = {key: copy.deepcopy(value) for key, value in item.items()
                          if key not in ("deadline_monotonic", "deadline_epoch")}
                public["remaining_seconds"] = max(0, item["deadline_monotonic"] - self.clock())
                items.append(public)
            return dict(schema_version=1, timeout_seconds=TIMEOUT_SECONDS,
                        observed_utc=utc(self.wall()), machine_active=self.machine_active,
                        quality=self.quality, active=bool(items), circuits=items,
                        remaining_seconds=min((item["remaining_seconds"] for item in items), default=None),
                        stop_state=self.stop_state, stop_error=self.stop_error,
                        automatic_stop_available=self.automatic_stop_available,
                        journal_durable=self.journal is not None and not self.journal_error,
                        journal_error=self.journal_error, journal=copy.deepcopy(self.events),
                        interpretation="Saved Fluides software indications; physical polarity needs commissioning")
