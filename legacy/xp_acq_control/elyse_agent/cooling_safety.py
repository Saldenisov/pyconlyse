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
import uuid

from .journal_worker import JournalWorker

TIMEOUT_SECONDS = 120.0
RECOVERY_SECONDS = 2.0
POLICY_VERSION = 2
JOURNAL_RECONCILIATION_CONFIRMATION = "ACKNOWLEDGE ALARM JOURNAL HISTORY GAP"
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
    """SQLite storage owned exclusively by JournalWorker, never an observer."""
    def __init__(self, path, namespace):
        parent = os.path.dirname(os.path.abspath(path))
        if not os.path.isdir(parent):
            os.makedirs(parent)
        self.lock = threading.RLock()
        self.namespace = namespace
        self.db = sqlite3.connect(path, check_same_thread=False)
        try:
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("CREATE TABLE IF NOT EXISTS cooling_state (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS cooling_events (id INTEGER PRIMARY KEY, name TEXT, payload TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS cooling_event_receipts (name TEXT, event_id TEXT, PRIMARY KEY(name,event_id))")
            self.db.execute("CREATE TABLE IF NOT EXISTS cooling_writer_state (name TEXT PRIMARY KEY, clean INTEGER NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS cooling_journal_recovery (name TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            self.db.commit()
        except Exception:
            self.db.close()
            raise

    def begin_session(self):
        with self.lock, self.db:
            row = self.db.execute("SELECT clean FROM cooling_writer_state WHERE name=?", (self.namespace,)).fetchone()
            warning = self.db.execute("SELECT payload FROM cooling_journal_recovery WHERE name=?", (self.namespace,)).fetchone()
            if warning is not None:
                warning = json.loads(warning[0])
                if (type(warning) is not dict or type(warning.get("required")) is not bool
                        or type(warning.get("reason")) is not str):
                    raise ValueError("Invalid persisted journal recovery state")
            if row is not None and row[0] != 1:
                warning = dict(required=True,
                    reason="Prior alarm journal writer did not close cleanly; unacknowledged events may be missing")
                self._store_recovery(warning)
            self.db.execute("INSERT OR REPLACE INTO cooling_writer_state VALUES (?,0)", (self.namespace,))
        return warning["reason"] if warning is not None and warning["required"] else ""

    def _store_recovery(self, value):
        self.db.execute("INSERT OR REPLACE INTO cooling_journal_recovery VALUES (?,?)",
                        (self.namespace, json.dumps(value, allow_nan=False)))

    def end_session(self, clean, uncertainty=""):
        with self.lock, self.db:
            if uncertainty:
                self._store_recovery(dict(required=True, reason=uncertainty))
            # Current writer cleanliness is independent of historical gaps.
            # Normal close never acknowledges or erases such a gap.
            self.db.execute("INSERT OR REPLACE INTO cooling_writer_state VALUES (?,?)",
                            (self.namespace, 1 if clean else 0))

    def load(self):
        with self.lock:
            row = self.db.execute("SELECT payload FROM cooling_state WHERE name=?", (self.namespace,)).fetchone()
            return json.loads(row[0]) if row else None

    def append(self, state, event):
        with self.lock, self.db:
            self._append(state, event)

    def _append(self, state, event):
        event_id = event.get("journal_event_id")
        if event_id is not None:
            row = self.db.execute("SELECT 1 FROM cooling_event_receipts WHERE name=? AND event_id=?",
                                  (self.namespace, event_id)).fetchone()
            if row is not None:
                return
        self.db.execute("INSERT OR REPLACE INTO cooling_state VALUES (?,?)",
                        (self.namespace, json.dumps(state, allow_nan=False)))
        self.db.execute("INSERT INTO cooling_events(name,payload) VALUES (?,?)",
                        (self.namespace, json.dumps(event, allow_nan=False)))
        if event_id is not None:
            self.db.execute("INSERT INTO cooling_event_receipts VALUES (?,?)", (self.namespace, event_id))

    def reconcile(self, state, event):
        if (event.get("kind") != "JOURNAL_HISTORY_RECONCILED"
                or event.get("confirmation") != JOURNAL_RECONCILIATION_CONFIRMATION):
            raise ValueError("Exact journal reconciliation audit event required")
        with self.lock, self.db:
            self._append(state, event)
            self._store_recovery(dict(required=False, reason="",
                reconciled_event_id=event["journal_event_id"],
                acknowledgment=dict(event_id=event["journal_event_id"],
                    observed_utc=event["observed_utc"], operator=event["operator"],
                    reason=event["reason"], reviewed_revision=event["reviewed_revision"],
                    missing_events_reconstructed=False)))

    def history_acknowledgment(self):
        """Read durable review metadata on the storage owner thread only."""
        with self.lock:
            row = self.db.execute("SELECT payload FROM cooling_journal_recovery WHERE name=?",
                                  (self.namespace,)).fetchone()
            if row is None:
                return None
            record = json.loads(row[0])
            if record.get("required") is not False:
                return None
            acknowledgment = record.get("acknowledgment")
            if acknowledgment is not None:
                if (type(acknowledgment) is not dict
                        or any(type(acknowledgment.get(name)) is not str
                               or not acknowledgment[name] for name in
                               ("event_id", "observed_utc", "operator", "reason"))
                        or type(acknowledgment.get("reviewed_revision")) is not int
                        or acknowledgment.get("missing_events_reconstructed") is not False):
                    raise ValueError("Invalid persisted journal acknowledgment")
            return copy.deepcopy(acknowledgment)

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
        capacity = kwargs.pop("journal_capacity", 64)
        if "journal" in kwargs:
            raise ValueError("with_journal owns its journal; external journal argument forbidden")
        # Validate/construct the policy before starting an owned non-daemon
        # thread. A failed subclass constructor must not orphan a writer.
        result = cls(**kwargs)
        return result.attach_owned_journal(path, namespace, capacity=capacity)

    @staticmethod
    def _validate_saved(saved, events):
        if type(events) is not list or any(type(event) is not dict for event in events):
            raise ValueError("Invalid persisted alarm event list")
        if saved is None:
            return
        if (type(saved) is not dict or type(saved.get("incidents")) is not dict
                or saved.get("stop_state") not in ("NONE", "REQUESTED", "INTERRUPTED", "UNAVAILABLE", "COMPLETED", "FAILED")
                or type(saved.get("stop_error", "")) is not str):
            raise ValueError("Invalid persisted alarm state")
        for name, item in saved["incidents"].items():
            if (name not in CIRCUITS or type(item) is not dict or item.get("circuit") != name
                    or type(item.get("deadline_epoch")) not in (int, float)
                    or not math.isfinite(item["deadline_epoch"])
                    or type(item.get("started_utc")) is not str
                    or type(item.get("deadline_utc")) is not str
                    or type(item.get("causes")) is not list):
                raise ValueError("Invalid persisted cooling incident")
        if (type(saved.get("policy_version", 1)) is not int
                or saved.get("policy_version", 1) not in (1, POLICY_VERSION)
                or type(saved.get("historical_incidents", [])) is not list):
            raise ValueError("Invalid persisted cooling policy version/history")
        for item in saved.get("historical_incidents", []):
            if type(item) is not dict or item.get("circuit") not in CIRCUITS:
                raise ValueError("Invalid persisted historical cooling incident")
        for item in saved["incidents"].values():
            if "incident_id" in item and (type(item["incident_id"]) is not str
                    or len(item["incident_id"]) != 32
                    or any(letter not in "0123456789abcdef" for letter in item["incident_id"])):
                raise ValueError("Invalid persisted cooling incident identity")
            if item.get("confirmation_eligible") is True:
                if (item.get("policy_version") != POLICY_VERSION
                        or type(item.get("confirmed")) is not bool
                        or (item["confirmed"] and (type(item.get("confirmed_by")) is not str
                            or not 1 <= len(item["confirmed_by"].strip()) <= 128
                            or type(item.get("confirmed_utc")) is not str))):
                    raise ValueError("Invalid persisted circulation confirmation")

    def __init__(self, clock=None, wall_clock=None, journal=None):
        self.clock, self.wall = clock or time.monotonic, wall_clock or time.time
        if not callable(self.clock) or not callable(self.wall):
            raise ValueError("Alarm clocks must be callable")
        self.journal = (journal if isinstance(journal, JournalWorker) or journal is None
                        else JournalWorker(lambda: journal, validate_loaded=self._validate_saved))
        self.lock = threading.RLock()
        self.incidents, self.recovering, self.events = {}, {}, []
        self.armed, self.arming = set(), {}
        self.historical_incidents = []
        self.experiment_session_id = None
        self.stop_state, self.stop_error = "NONE", ""
        self.journal_error = ""
        self._journal_loaded = False
        self._local_stop_changed = False
        self._observation_started = False
        self._journal_revision = 0
        self.automatic_stop_available = False
        self.machine_active = None
        self.quality = "UNKNOWN"
        self._sync_journal()

    def attach_owned_journal(self, path, namespace, capacity=64):
        """Attach storage once, before this cold policy receives observations.

        The composition root can bind its unique process/network guard first,
        then start the journal owner without replacing the shared RAM policy.
        No observed incidents or decisions may be overwritten by a late load.
        """
        with self.lock:
            if (self.journal is not None or self._observation_started
                    or self._journal_loaded or self._local_stop_changed
                    or self._journal_revision or self.incidents or self.recovering
                    or self.events or self.stop_state != "NONE" or self.stop_error
                    or self.machine_active is not None or self.quality != "UNKNOWN"
                    or self.automatic_stop_available):
                raise RuntimeError("Alarm journal can attach only to a pristine cold policy")
            self.journal = JournalWorker(lambda: AlarmJournal(path, namespace),
                validate_loaded=self._validate_saved, capacity=capacity)
            self.journal_error = "Alarm journal initial load pending"
            return self

    def _state_image(self):
        return dict(incidents=self.incidents, stop_state=self.stop_state,
                    stop_error=self.stop_error, policy_version=POLICY_VERSION,
                    experiment_session_id=self.experiment_session_id,
                    historical_incidents=self.historical_incidents)

    def bind_experiment_session(self, session_id):
        """Bind this cold runtime's software episodes, never claim hardware OFF.

        Previous-boot stop results remain audited history. Native ownership
        recovery is separate and is neither acknowledged nor changed here.
        This RAM declaration can precede attaching the owned journal.
        """
        if (type(session_id) is not str or len(session_id) != 32
                or any(char not in "0123456789abcdef" for char in session_id)):
            raise ValueError("Exact experiment session required")
        with self.lock:
            if self.experiment_session_id not in (None, session_id):
                raise RuntimeError("Cooling experiment session cannot be replaced")
            if self.experiment_session_id == session_id:
                return
            self.experiment_session_id = session_id
            self._sync_journal()
            if self.incidents or self.stop_state != "NONE":
                self._retire_inactive_incidents("PRIOR_EXPERIMENT_SESSION")

    def _retire_inactive_incidents(self, reason):
        previous_state, previous_error = self.stop_state, self.stop_error
        retired = []
        for item in self.incidents.values():
            item = copy.deepcopy(item)
            item.update(historical=True, countdown_required=False, historical_reason=reason,
                prior_stop_state=previous_state, prior_stop_error=previous_error,
                reclassified_utc=utc(self.wall()))
            self.historical_incidents.append(item)
            retired.append(item)
        self.incidents.clear()
        self.recovering.clear()
        self.armed.clear()
        self.arming.clear()
        self.stop_state, self.stop_error = "NONE", ""
        if retired or previous_state != "NONE":
            self._local_stop_changed = True
            self._event("EXPERIMENT_COOLING_EPISODES_ARCHIVED", reason=reason,
                historical_incidents=retired, prior_stop_state=previous_state,
                prior_stop_error=previous_error, hardware_off_confirmed=False,
                history_deleted=False)

    @staticmethod
    def _legacy_incident_id(item):
        # Historical, unconfirmable identities stay stable without arming a
        # new process or changing an old journal merely to assign an ID.
        value = {key: item.get(key) for key in ("circuit", "started_utc", "deadline_utc", "causes")}
        return uuid.uuid5(uuid.NAMESPACE_URL,
                         json.dumps(value, sort_keys=True, allow_nan=False)).hex

    def _sync_journal(self):
        """Short RAM-only status exchange; never calls SQLite or waits on I/O."""
        if self.journal is None:
            return None
        loaded = self.journal.loaded() if not self._journal_loaded else None
        if loaded is not None:
            saved, events = loaded
            migrated, retained_loaded = [], False
            if saved is not None:
                self.historical_incidents = copy.deepcopy(saved.get("historical_incidents", []))
                for name, item in saved["incidents"].items():
                    item.setdefault("incident_id", self._legacy_incident_id(item))
                    prior_session = (self.experiment_session_id is not None
                        and saved.get("experiment_session_id") != self.experiment_session_id)
                    if prior_session or (saved.get("policy_version", 1) < POLICY_VERSION
                            and item["causes"] and all(isinstance(cause, dict) and cause.get("signal") == "220V"
                                    for cause in item["causes"])):
                        item.update(historical=True, countdown_required=False,
                            historical_reason=("PRIOR_EXPERIMENT_SESSION" if prior_session
                                else "PRE_POLICY_2_220V_STARTUP_INDICATION"),
                            prior_stop_state=saved["stop_state"], prior_stop_error=saved.get("stop_error", ""),
                            reclassified_utc=utc(self.wall()))
                        self.historical_incidents.append(copy.deepcopy(item))
                        migrated.append(item)
                        continue
                    retained_loaded = True
                    item["confirmation_eligible"] = (item.get("confirmation_eligible") is True
                        and item.get("policy_version") == POLICY_VERSION)
                    if item["confirmation_eligible"] is not True:
                        item.update(confirmed=False, confirmed_by=None, confirmed_utc=None)
                    item.setdefault("confirmed", False)
                    item.setdefault("confirmed_by", None)
                    item.setdefault("confirmed_utc", None)
                    remaining = item["deadline_epoch"] - self.wall()
                    # Backward wall-clock steps never grant a new grace period.
                    if remaining > TIMEOUT_SECONDS:
                        remaining = 0
                    item["deadline_monotonic"] = self.clock() + max(0, remaining)
                    current = self.incidents.get(name)
                    if current is None or item["deadline_monotonic"] <= current["deadline_monotonic"]:
                        self.incidents[name] = item
                    self.recovering.pop(name, None)
                if not self._local_stop_changed:
                    self.stop_state, self.stop_error = saved["stop_state"], saved.get("stop_error", "")
                    # A previous queued request is never a completed stop.
                    if self.stop_state == "REQUESTED":
                        self.stop_state = "INTERRUPTED"
                    if migrated and not retained_loaded:
                        self.stop_state, self.stop_error = "NONE", ""
            self.events = (events + self.events)[-100:]
            self._journal_revision += 1
            self._journal_loaded = True
            self.journal.adopt_loaded(self._state_image())
            for item in migrated:
                self._event("PRIOR_EXPERIMENT_INCIDENT_ARCHIVED" if item["historical_reason"]
                            == "PRIOR_EXPERIMENT_SESSION" else "LEGACY_220V_INCIDENT_RECLASSIFIED", item["circuit"],
                    incident_id=item["incident_id"], policy_version=POLICY_VERSION,
                    prior_policy_version=saved.get("policy_version", 1),
                    prior_stop_state=saved["stop_state"], prior_stop_error=saved.get("stop_error", ""),
                    historical_incident=copy.deepcopy(item), history_deleted=False)
            if (saved is not None and self.experiment_session_id is not None
                    and saved.get("experiment_session_id") != self.experiment_session_id
                    and not self.incidents and self.stop_state != "NONE"):
                self._retire_inactive_incidents("PRIOR_EXPERIMENT_SESSION")
        status = self.journal.status()
        self.journal_error = status["error"]
        return status

    def _event(self, kind, circuit=None, **extra):
        event = dict(kind=kind, circuit=circuit, observed_utc=utc(self.wall()), **extra)
        self.events = (self.events + [event])[-100:]
        self._journal_revision += 1
        if self.journal is not None:
            self.journal.append(self._state_image(), event)
            self._sync_journal()

    def observe(self, circuits, machine_active, observation_id=None):
        with self.lock:
            self._observation_started = True
            self._sync_journal()
            was_active = self.machine_active
            self.machine_active = machine_active
            self.quality = "FRESH" if all(c.get("quality") == "FRESH" for c in circuits.values()) else "UNKNOWN"
            if machine_active is not True:
                self.armed.clear()
                self.arming.clear()
            if (machine_active is False and self.experiment_session_id is not None
                    and self.stop_state != "REQUESTED" and (self.incidents or self.stop_state != "NONE")):
                self._retire_inactive_incidents("HT_EXPERIMENT_INACTIVE")
            if (self.experiment_session_id is not None and machine_active is True
                    and was_active is not True):
                # Runtime True now means qualified HT has actually appeared.
                # Existing red at that point needs the same operator decision
                # as a later green->red transition, without a startup timer.
                self.armed.update(CIRCUITS)
            for name, reading in circuits.items():
                if name not in CIRCUITS:
                    raise ValueError("Unknown cooling circuit")
                item = self.incidents.get(name)
                if reading["fault"] is True:
                    self.recovering.pop(name, None)
                    self.arming.pop(name, None)
                    if (item is None and machine_active is True and name in self.armed
                            and reading.get("quality") == "FRESH"):
                        now, wall = self.clock(), self.wall()
                        self.incidents[name] = dict(circuit=name, incident_id=uuid.uuid4().hex,
                            policy_version=POLICY_VERSION, confirmation_eligible=True,
                            confirmed=False, confirmed_by=None, confirmed_utc=None, started_utc=utc(wall),
                            deadline_utc=utc(wall + TIMEOUT_SECONDS), deadline_epoch=wall + TIMEOUT_SECONDS,
                            deadline_monotonic=now + TIMEOUT_SECONDS, causes=copy.deepcopy(reading["causes"]))
                        self.armed.discard(name)
                        self._event("CIRCULATION_LOST", name, causes=reading["causes"],
                                    incident_id=self.incidents[name]["incident_id"], policy_version=POLICY_VERSION)
                elif item is not None and reading["fault"] is False and reading["quality"] == "FRESH":
                    previous = self.recovering.get(name)
                    if previous is None:
                        self.recovering[name] = (self.clock(), observation_id)
                    elif (self.clock() - previous[0] >= RECOVERY_SECONDS
                          and observation_id is not None and observation_id != previous[1]
                          and self.stop_state in ("NONE", "COMPLETED")
                          and (self.journal is None or self._journal_loaded)):
                        restored = self.incidents.pop(name)
                        self.recovering.pop(name, None)
                        if machine_active is True:
                            self.armed.add(name)
                        if not self.incidents:
                            self.stop_state, self.stop_error = "NONE", ""
                        self._event("CIRCULATION_RESTORED", name, incident_id=restored["incident_id"],
                                    confirmed_by=restored.get("confirmed_by"))
                else:
                    self.recovering.pop(name, None)
                    if (item is None and machine_active is True and reading["fault"] is False
                            and reading.get("quality") == "FRESH" and name not in self.armed):
                        previous = self.arming.get(name)
                        if previous is None:
                            self.arming[name] = (self.clock(), observation_id)
                        elif (self.clock() - previous[0] >= RECOVERY_SECONDS
                                and observation_id is not None and observation_id != previous[1]):
                            self.armed.add(name)
                            self.arming.pop(name, None)
                    else:
                        self.arming.pop(name, None)

    def tick(self, automatic_stop_available=False):
        """Return one stop request, never a hardware command or process exit."""
        with self.lock:
            self._sync_journal()
            scope_active = self.experiment_session_id is None or self.machine_active is True
            self.automatic_stop_available = automatic_stop_available is True and scope_active
            due = scope_active and any(item.get("confirmed") is not True and self.clock() >= item["deadline_monotonic"]
                      for item in self.incidents.values())
            if due and self.stop_state in ("NONE", "UNAVAILABLE", "INTERRUPTED"):
                if self.automatic_stop_available:
                    self.stop_state = "REQUESTED"
                    self._local_stop_changed = True
                    self._event("SHUTDOWN_REQUESTED")
                    return True
                if self.stop_state == "NONE":
                    self.stop_state = "UNAVAILABLE"
                    self._local_stop_changed = True
                    self._event("SHUTDOWN_UNAVAILABLE")
            return False

    def stop_result(self, error=""):
        with self.lock:
            self._sync_journal()
            self.stop_state = "FAILED" if error else "COMPLETED"
            self._local_stop_changed = True
            self.stop_error = str(error)
            self._event("SHUTDOWN_FAILED" if error else "SHUTDOWN_COMPLETED", error=str(error))

    def confirm_circulation(self, incident_ids, operator):
        """Suppress only these additional Python countdowns, without NI I/O.

        Admission is atomic for the exact current incidents. It neither clears
        red indications nor extends deadlines, proves flow, or cancels a stop
        already requested/queued. Journal admission is not a durable commit ACK.
        """
        if (type(incident_ids) is not list or not incident_ids
                or any(type(value) is not str or len(value) != 32
                    or any(letter not in "0123456789abcdef" for letter in value) for value in incident_ids)
                or len(set(incident_ids)) != len(incident_ids)
                or type(operator) is not str or not 1 <= len(operator.strip()) <= 128):
            raise ValueError("Exact unique active incident IDs and authenticated operator required")
        with self.lock:
            self._sync_journal()
            now = self.clock()
            by_id = dict((item.get("incident_id"), item) for item in self.incidents.values())
            if (self.stop_state != "NONE" or any(value not in by_id
                    or by_id[value].get("confirmation_eligible") is not True
                    or by_id[value].get("confirmed") is True
                    or now >= by_id[value]["deadline_monotonic"] for value in incident_ids)):
                raise RuntimeError("Circulation confirmation requires exact active unexpired incidents before stop admission")
            stamp, operator = utc(self.wall()), operator.strip()
            for value in incident_ids:
                by_id[value].update(confirmed=True, confirmed_by=operator, confirmed_utc=stamp)
            self._event("CIRCULATION_CONFIRMED_BY_OPERATOR", incident_ids=list(incident_ids),
                        operator=operator, confirmed_utc=stamp, policy_version=POLICY_VERSION,
                        deadlines_extended=False, physical_circulation_verified=False)
            return dict(accepted=True, incident_ids=list(incident_ids), confirmed_by=operator,
                        confirmed_utc=stamp, hardware_acknowledged=False,
                        physical_circulation_verified=False, deadline_extended=False)

    def snapshot(self):
        with self.lock:
            journal = self._sync_journal()
            items, candidates = [], []
            now = self.clock()
            for item in self.incidents.values():
                public = {key: copy.deepcopy(value) for key, value in item.items()
                          if key not in ("deadline_monotonic", "deadline_epoch")}
                public["remaining_seconds"] = max(0, item["deadline_monotonic"] - now)
                public["confirmed"] = item.get("confirmed") is True
                public["confirmed_by"] = item.get("confirmed_by")
                public["confirmed_utc"] = item.get("confirmed_utc")
                public["countdown_required"] = not public["confirmed"]
                items.append(public)
                if (public["countdown_required"] and item.get("confirmation_eligible") is True
                        and self.stop_state == "NONE" and public["remaining_seconds"] > 0):
                    candidates.append(dict(incident_id=item["incident_id"], circuit=item["circuit"],
                        deadline_utc=item["deadline_utc"], remaining_seconds=public["remaining_seconds"]))
            return dict(schema_version=1, policy_version=POLICY_VERSION, timeout_seconds=TIMEOUT_SECONDS,
                        experiment_session_id=self.experiment_session_id,
                        observed_utc=utc(self.wall()), machine_active=self.machine_active,
                        quality=self.quality, active=bool(items), circuits=items,
                        countdown_required=any(item["countdown_required"] for item in items),
                        confirmation_required=bool(candidates), confirmation_candidates=candidates,
                        armed_circuits=sorted(self.armed),
                        historical_incidents=copy.deepcopy(self.historical_incidents),
                        remaining_seconds=min((item["remaining_seconds"] for item in items
                                               if item["countdown_required"]), default=None),
                        stop_state=self.stop_state, stop_error=self.stop_error,
                        automatic_stop_available=self.automatic_stop_available,
                        journal_required=self.journal is not None,
                        journal_durable=bool(journal and journal["durable"]),
                        journal_ready=bool(journal and self._journal_loaded),
                        journal_write_ready=bool(journal and journal["write_ready"]),
                        journal_storage_error=journal["storage_error"] if journal else "",
                        journal_pending=journal["pending"] if journal else 0,
                        journal_submitted=journal["submitted"] if journal else 0,
                        journal_committed=journal["committed"] if journal else 0,
                        journal_overflow=journal["overflow"] if journal else 0,
                        journal_revision=self._journal_revision,
                        journal_recovery_required=bool(journal and journal["recovery_error"]),
                        journal_reconciliation_pending=bool(journal and journal["reconciling"]),
                        journal_history_warning=journal["recovery_error"] if journal else "",
                        journal_history_acknowledge_available=bool(journal and self._journal_loaded
                            and journal["recovery_error"] and journal["write_ready"]),
                        journal_history_acknowledgment_pending=bool(journal and journal["reconciling"]),
                        journal_history_acknowledged=bool(journal and journal["history_acknowledgment"]),
                        journal_history_acknowledgment=copy.deepcopy(journal["history_acknowledgment"])
                            if journal else None,
                        journal_error=self.journal_error, journal=copy.deepcopy(self.events),
                        interpretation="Saved Fluides software indications; physical polarity needs commissioning")

    def reconcile_journal(self, confirmation, qualified_local=False,
                          operator=None, reason=None, expected_revision=None):
        """Qualified local review only, never an HTTP/hardware command.

        Acknowledge reviewed historical uncertainty without clearing incidents
        or changing deadlines. Success returns an admission receipt, not a
        durability ACK; the warning clears only after the atomic audit commit.
        """
        if (qualified_local is not True or confirmation != JOURNAL_RECONCILIATION_CONFIRMATION
                or type(operator) is not str or not 1 <= len(operator.strip()) <= 128
                or type(reason) is not str or not 1 <= len(reason.strip()) <= 512):
            raise ValueError("Exact confirmation, qualified local operator and reconciliation reason required")
        with self.lock:
            self._sync_journal()
            if (self.journal is None or not self._journal_loaded
                    or type(expected_revision) is not int or expected_revision != self._journal_revision):
                raise RuntimeError("Loaded unchanged alarm state must be reviewed before reconciliation")
            event = dict(kind="JOURNAL_HISTORY_RECONCILED", circuit=None,
                         observed_utc=utc(self.wall()), operator=operator.strip(),
                         reason=reason.strip(), confirmation=confirmation,
                         qualified_local=True, reviewed_revision=expected_revision,
                         prior_history_warning=self.journal.status()["recovery_error"],
                         missing_events_reconstructed=False)
            receipt = self.journal.reconcile(self._state_image(), event)
            self.events = (self.events + [event])[-100:]
            self._journal_revision += 1
            self._sync_journal()
            return receipt

    def acknowledge_journal_history(self, qualified_local=False, operator=None,
                                    reason=None, expected_revision=None):
        """Admit explicit LOCAL historical-warning review; never repair history.

        A local UI must show the current warning/incident state before asking
        for acknowledgment, then pass that snapshot's journal_revision. The
        returned receipt is admission only. Poll journal_history_warning and
        journal_history_acknowledgment_pending for the durable result. Current
        storage failures remain errors; active incidents/deadlines are retained.
        """
        return self.reconcile_journal(JOURNAL_RECONCILIATION_CONFIRMATION,
            qualified_local=qualified_local, operator=operator, reason=reason,
            expected_revision=expected_revision)

    def close(self, timeout=0):
        """Drain/join outside runtime locks; False retains writer ownership."""
        with self.lock:
            self._sync_journal()
            journal = self.journal
        return True if journal is None else journal.close(timeout)
