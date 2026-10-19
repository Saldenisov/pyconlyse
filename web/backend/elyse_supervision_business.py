"""Durable Supervision intent lifecycle, with an injectable external ACQ boundary.

No DAQ sequencing or network transport lives here. The default port is disconnected.
Only a test/simulation port may submit in this revision; a production adapter needs
hardware authorization and an atomic revision check on the ACQ side first.
"""

import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from elyse_supervision_service import json_value, model
from elyse_acq_transport import AcqRejected
from legacy.xp_acq_agent.elyse_agent.supervision_setpoints import rules as setpoint_rules, finite_number, adjusted
from legacy.xp_acq_agent.elyse_agent.supervision_lifecycle import CATALOG as LIFECYCLE_CATALOG, STATES as LIFECYCLE_STATES

ACQ_HOST = "10.20.30.10"
ACK_TIMEOUT_SECONDS = 15
ACTIVE = ("SUBMITTING", "ACCEPTED", "RUNNING", "UNKNOWN")
TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED")


class AcqPort(Protocol):
    """Adapter boundary: bounded I/O, authoritative state, atomic acceptance.

    ``read_state`` returns the normalized envelope validated below. Submission must
    compare session/revision atomically at ACQ, enforce its own hardware guards,
    deduplicate intent IDs, and return a matching run acknowledgement. Neither an
    HTTP URL nor a Tango device name is assumed. The configured signed TCP
    simulator implements this boundary; production ports remain blocked.
    """

    host: str
    mode: str

    def read_state(self) -> dict: ...

    def submit_procedure(self, *, intent_id: str, procedure: str,
                         expected_revision: str, session_id: str) -> dict: ...


class BusinessConflict(ValueError):
    pass


class BusinessBlocked(ValueError):
    pass


class DisconnectedAcq:
    host = ACQ_HOST
    mode = "UNCONFIGURED"

    def read_state(self):
        raise ConnectionError("ACQ transport not configured; no endpoint assumed")


def catalog(simulated_plans=False, simulated_setpoints=False, simulated_lifecycle=False):
    """Reuse recovered field crosswalks; do not accept arbitrary ACQ procedures."""
    from DeviceServers.control.elyse_acq.dps_bridge import resolve_dps_request

    commands = model("page_command_events")
    parameters = model("parameter_page_events")
    mappings = [(p.value, fields) for p, fields in parameters.PROCEDURE_FIELD_MAPS.items()]
    mappings += [
        (commands.CommandPage.ALIMENTATIONS.value, commands.ALIMENTATIONS_FIELD_MAP),
        (commands.CommandPage.MODULATOR.value, commands.MODULATOR_FIELD_MAP),
    ]
    entries = []
    for page, fields in mappings:
        for control, field in fields:
            index = commands.DPS_FIELDS.index(field)
            plan = resolve_dps_request(index, True)
            entries.append(dict(
                page=page, control=control, kind="PROCEDURE", dps_index=index,
                procedure=plan.name, legacy_event_case=plan.legacy_event_case,
                blocked_reason=("Magnet ownership unresolved; legacy DAQmx fallback forbidden"
                                if page == commands.CommandPage.ALIMENTATIONS.value and not simulated_plans else ""),
            ))
            if simulated_plans:
                entries[-1]["hardware_blocked_reason"] = (
                    "Magnet ownership unresolved; no physical DAQ adapter" if page == commands.CommandPage.ALIMENTATIONS.value
                    else "Hardware execution disabled; simulation only")
    for rule in parameters.PARAMETER_RULES:
        portable = next(item for item in setpoint_rules() if item["page"] == rule.page.value and item["control"] == rule.arrow)
        entries.append(dict(
            page=rule.page.value, control=rule.arrow, kind="SETPOINT",
            numeric_field=rule.numeric_field, delta=rule.delta,
            native_limits=json_value(rule.limits),
            blocked_reason="" if simulated_setpoints else "ACQ setpoint API and physical limits not commissioned",
            procedure=portable["procedure"], target=portable["target"],
            hardware_blocked_reason="Physical limits and units not commissioned; simulation only",
        ))
    if simulated_lifecycle:
        entries += [dict(entry, lifecycle=True) for entry in LIFECYCLE_CATALOG]
    return entries


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("ACQ observed_at must be an aware ISO timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("ACQ timestamp requires timezone")
    return result.astimezone(timezone.utc)


def validate_acq_state(value, now, max_age):
    """Normalized adapter contract, not the existing Tango facade's wire format."""
    keys = {"session_id", "revision", "observed_at", "quality", "dps", "run"}
    if type(value) is not dict or set(value) != keys:
        raise ValueError("ACQ state contract requires session_id, revision, observed_at, quality, dps, run")
    for key in ("session_id", "revision"):
        if not isinstance(value[key], str) or not 1 <= len(value[key]) <= 128:
            raise ValueError(f"ACQ {key} must be a nonempty bounded string")
    if value["quality"] != "SIMULATED":
        raise ValueError("Only explicitly SIMULATED ACQ state is commissioned")
    age = (now - _timestamp(value["observed_at"])).total_seconds()
    if age < 0 or age > max_age:
        raise ValueError("ACQ state stale or timestamp in future")
    dps = value["dps"]
    if type(dps) is not list or len(dps) != 29 or any(type(bit) is not bool for bit in dps):
        raise ValueError("ACQ DPS must contain exactly 29 Boolean fields")
    _validate_run(value["run"])
    return value


def _validate_run(run):
    if type(run) is not dict or set(run) != {"state", "intent_id", "procedure", "error"}:
        raise ValueError("ACQ run requires state, intent_id, procedure, error")
    if run["state"] not in ("IDLE", "ACCEPTED", "RUNNING", "UNKNOWN", *TERMINAL):
        raise ValueError("Unknown ACQ run state")
    if any(not isinstance(run[key], str) or len(run[key]) > 4096
           for key in ("intent_id", "procedure", "error")):
        raise ValueError("Invalid ACQ run strings")
    if run["state"] != "IDLE" and (not run["intent_id"] or not run["procedure"]):
        raise ValueError("ACQ acknowledgement requires intent and procedure")


class SupervisionBusiness:
    def __init__(self, path, acq=None, clock=None, max_age_seconds=5):
        self.path = str(path)
        self.acq = acq or DisconnectedAcq()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        if (type(max_age_seconds) not in (int, float)
                or not math.isfinite(max_age_seconds) or max_age_seconds <= 0):
            raise ValueError("Positive finite freshness limit required")
        self.max_age = max_age_seconds
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS supervision_intents (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id TEXT UNIQUE NOT NULL,
                    request_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS supervision_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
            """)
            db.execute("BEGIN IMMEDIATE")
            if "kind" not in {row["name"] for row in db.execute("PRAGMA table_info(supervision_intents)")}:
                db.execute("ALTER TABLE supervision_intents ADD COLUMN kind TEXT NOT NULL DEFAULT 'PROCEDURE'")
                for row in db.execute("SELECT intent_id,plan_json FROM supervision_intents").fetchall():
                    db.execute("UPDATE supervision_intents SET kind=? WHERE intent_id=?",
                               (json.loads(row["plan_json"])["kind"], row["intent_id"]))
            # Arrows have their own brief flight, and may overlap a procedure.
            # An UNKNOWN outcome in either lane blocks both at admission.
            db.execute("DROP INDEX IF EXISTS supervision_single_flight")
            db.execute("""CREATE UNIQUE INDEX supervision_single_flight ON supervision_intents ((1))
                WHERE kind='PROCEDURE' AND state IN ('SUBMITTING','ACCEPTED','RUNNING','UNKNOWN')""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS supervision_single_setpoint ON supervision_intents ((1))
                WHERE kind='SETPOINT' AND state IN ('SUBMITTING','ACCEPTED','RUNNING','UNKNOWN')""")

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _now(self):
        return self.clock().astimezone(timezone.utc).isoformat()

    def _event(self, db, intent_id, state, message):
        db.execute("INSERT INTO supervision_events(intent_id,state,message,recorded_at) VALUES (?,?,?,?)",
                   (intent_id, state, message, self._now()))

    @staticmethod
    def _item(row):
        return dict(intent_id=row["intent_id"], request=json.loads(row["request_json"]),
                    plan=json.loads(row["plan_json"]), state=row["state"], error=row["error"],
                    created_at=row["created_at"], updated_at=row["updated_at"])

    def intent(self, intent_id):
        with self._db() as db:
            row = db.execute("SELECT * FROM supervision_intents WHERE intent_id=?", (intent_id,)).fetchone()
        if row is None:
            raise KeyError("Unknown supervision intent")
        return self._item(row)

    def stage(self, request):
        if type(request) is not dict or set(request) not in ({"intent_id", "page", "control"}, {"intent_id", "page", "control", "base_value"}):
            raise ValueError("Required fields: intent_id, page, control")
        intent_id = request["intent_id"]
        if not isinstance(intent_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", intent_id):
            raise ValueError("Invalid intent_id")
        match = next((item for item in self._catalog()
                      if item["page"] == request["page"] and item["control"] == request["control"]), None)
        if match is None:
            raise ValueError("Unknown page/control; raw procedures and I/O are not accepted")
        if "base_value" in request:
            if match["kind"] != "SETPOINT":
                raise ValueError("base_value belongs only to a named setpoint")
            finite_number(request["base_value"])
            match = dict(match, requested_value=adjusted(match, request["base_value"]))
        elif match["kind"] == "SETPOINT" and not match["blocked_reason"]:
            raise ValueError("Explicit finite numeric base_value required; no default zero")
        canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM supervision_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if prior:
                if prior["request_json"] != canonical:
                    raise BusinessConflict("intent_id already belongs to a different request")
                return self._item(prior)
            now = self._now()
            db.execute("""INSERT INTO supervision_intents
                (intent_id,request_json,plan_json,state,created_at,updated_at,kind) VALUES (?,?,?,'DRAFT',?,?,?)""",
                       (intent_id, canonical, json.dumps(match, ensure_ascii=False), now, now, match["kind"]))
            self._event(db, intent_id, "DRAFT", "Operator intent saved; no ACQ submission")
        return self.intent(intent_id)

    def _catalog(self):
        return catalog(simulated_plans=self.acq.mode == "SIMULATION"
                       and getattr(self.acq, "simulates_all_plans", False) is True,
                       simulated_setpoints=self.acq.mode == "SIMULATION"
                       and getattr(self.acq, "simulates_setpoints", False) is True,
                       simulated_lifecycle=self.acq.mode == "SIMULATION"
                       and getattr(self.acq, "simulates_lifecycle", False) is True)

    def _read(self):
        try:
            if self.acq.host != ACQ_HOST:
                raise ValueError("Unexpected ACQ host")
            if self.acq.mode != "SIMULATION":
                raise ConnectionError("ACQ transport not configured; production submission disabled")
            observe = getattr(self.acq, "read_observation", None)
            if callable(observe):
                observation = observe()
                if type(observation) is not dict or set(observation) != {"state", "lifecycle", "setpoints"}:
                    raise ValueError("Malformed atomic ACQ observation")
                value = dict(validate_acq_state(observation["state"], self.clock(), self.max_age))
                value["_observation"] = observation  # Request-local, never a shared cache or wire state.
            else:
                value = validate_acq_state(self.acq.read_state(), self.clock(), self.max_age)
            return value, ""
        except Exception as error:
            # External adapter failures never become healthy/idle telemetry.
            return None, str(error)[:4096]

    def _update(self, db, intent_id, state, error, message):
        db.execute("UPDATE supervision_intents SET state=?,error=?,updated_at=? WHERE intent_id=?",
                   (state, error, self._now(), intent_id))
        self._event(db, intent_id, state, message)

    def _reconcile(self, sample):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT * FROM supervision_intents WHERE state IN (?,?,?,?)", ACTIVE).fetchall()
            for row in rows:
                if row["session_id"] != sample["session_id"]:
                    if row["state"] != "UNKNOWN":
                        self._update(db, row["intent_id"], "UNKNOWN", "ACQ session changed; outcome unresolved",
                                     "ACQ restarted; no automatic resubmission")
                    continue
                run = sample["run"]
                if run["intent_id"] != row["intent_id"] or run["procedure"] != json.loads(row["plan_json"]).get("procedure"):
                    continue  # Unrelated/idle run is not an acknowledgement.
                if run["state"] == "IDLE" or (row["state"] == "RUNNING" and run["state"] == "ACCEPTED"):
                    continue
                if row["state"] != run["state"] or row["error"] != run["error"]:
                    self._update(db, row["intent_id"], run["state"], run["error"],
                                 "Matching ACQ acknowledgement; not physical readback")

    def _reconcile_history(self, sample):
        lookup = getattr(self.acq, "read_intent", None)
        if not callable(lookup):
            return
        with self._db() as db:
            rows = db.execute("SELECT * FROM supervision_intents WHERE state IN (?,?,?,?)", ACTIVE).fetchall()
        for row in rows:
            self._reconcile_history_item(row, sample, lookup)

    def _reconcile_history_item(self, row, sample, lookup):
        if row is None or (row["session_id"] == sample["session_id"]
                           and sample["run"]["intent_id"] == row["intent_id"]):
            return
        try:
            history = lookup(row["intent_id"])
            if type(history) is not dict or set(history) != {"session_id", "run"}:
                return
            _validate_run(history["run"])
            run = history["run"]
            if (history["session_id"] != row["session_id"] or run["intent_id"] != row["intent_id"]
                    or run["procedure"] != json.loads(row["plan_json"])["procedure"]
                    or run["state"] not in TERMINAL):
                return
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT state FROM supervision_intents WHERE intent_id=?", (row["intent_id"],)).fetchone()
                if current["state"] in ACTIVE:
                    self._update(db, row["intent_id"], run["state"], run["error"],
                                 "Durable ACQ terminal acknowledgement; original session verified")
        except Exception:
            return  # History lookup failure cannot release exclusion or trigger a send.

    def _phase_trace(self, items, active):
        lookup = getattr(self.acq, "trace", None)
        selected = active["intent_id"] if active else next(
            (item["intent_id"] for item in items if item["state"] in TERMINAL), None)
        if not selected or not callable(lookup):
            return None, [], ""
        try:
            phases = lookup(selected)
            keys = {"step_index", "operation", "outcome", "detail", "recorded_at"}
            if type(phases) is not list or len(phases) > 512:
                raise ValueError("ACQ phase trace must be a bounded list")
            for phase in phases:
                if (type(phase) is not dict or set(phase) != keys
                        or type(phase["step_index"]) is not int or not -1 <= phase["step_index"] <= 255
                        or phase["outcome"] not in {"STARTED", "ACCEPTED", "RUNNING", "UNKNOWN", *TERMINAL}
                        or type(phase["detail"]) is not dict or not isinstance(phase["operation"], str)
                        or len(phase["operation"]) > 128):
                    raise ValueError("Malformed ACQ phase trace")
                _timestamp(phase["recorded_at"])
            return selected, phases, ""
        except Exception as error:
            return selected, [], str(error)[:4096]  # Trace failure never changes admission or outcome.

    def intent_trace(self, intent_id):
        item = self.intent(intent_id)
        selected, phases, error = self._phase_trace([item], {"intent_id": intent_id})
        return dict(schema_version=1, execution_allowed=False, physical_status="NOT_EXECUTED",
                    intent_id=selected, phases=phases, error=error)

    def snapshot(self):
        # A worker may die between durable admission and the remote call. Retain
        # exclusion, but do not present an unacknowledged old send as live progress.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            for pending in db.execute("SELECT * FROM supervision_intents WHERE state='SUBMITTING'").fetchall():
                if (self.clock() - _timestamp(pending["updated_at"])).total_seconds() > ACK_TIMEOUT_SECONDS:
                    self._update(db, pending["intent_id"], "UNKNOWN", "No matching acknowledgement within 15 s",
                                 "Unacknowledged submission retained; no automatic retry")
        sample, error = self._read()
        if sample:
            self._reconcile_history(sample)
            self._reconcile(sample)
        with self._db() as db:
            items = [self._item(row) for row in db.execute(
                "SELECT * FROM supervision_intents ORDER BY seq DESC LIMIT 50")]
            active_rows = db.execute("SELECT * FROM supervision_intents WHERE state IN (?,?,?,?) ORDER BY seq", ACTIVE).fetchall()
            for row in active_rows:
                if not any(item["intent_id"] == row["intent_id"] for item in items):
                    items.insert(0, self._item(row))
            events = [dict(row) for row in db.execute("SELECT * FROM supervision_events ORDER BY seq DESC LIMIT 100")]
        active = active_rows[0] if active_rows else None
        busy = bool(active_rows or (sample and (any(sample["dps"]) or sample["run"]["state"] in ("ACCEPTED", "RUNNING", "UNKNOWN"))))
        unresolved = any(row["state"] == "UNKNOWN" for row in active_rows) or bool(sample and sample["run"]["state"] == "UNKNOWN")
        setpoints, setpoint_error = self._read_setpoints(sample) if sample else (None, "")
        cycle, cycle_error = self._read_lifecycle(sample) if sample else (None, "ACQ unavailable")
        cycle_blocks = cycle_error or (cycle and cycle["state"] not in ("UNMANAGED", "RUNNING"))
        arrow_busy = any(row["kind"] == "SETPOINT" for row in active_rows)
        trace_id, phases, trace_error = self._phase_trace(items, active) if sample else (None, [], "")
        return dict(
            schema_version=1, execution_allowed=False, physical_status="NOT_EXECUTED",
            mode="SUPERVISION_BUSINESS", catalog=self._catalog(), intents=items, events=events,
            active_intent_id=active["intent_id"] if active else None,
            submission_allowed=bool(sample and not busy), busy=busy,
            setpoint_submission_allowed=bool(setpoints and not unresolved and not arrow_busy and not cycle_blocks),
            acq=dict(host=ACQ_HOST, mode=self.acq.mode, quality=sample["quality"] if sample else "UNAVAILABLE",
                     endpoint=getattr(self.acq, "endpoint", None),
                     setpoints=setpoints["values"] if setpoints else {}, setpoint_error=setpoint_error,
                     lifecycle=cycle, lifecycle_error=cycle_error,
                     trace_intent_id=trace_id, phases=phases, trace_error=trace_error,
                     revision=sample["revision"] if sample else None,
                     observed_at=sample["observed_at"] if sample else None, error=error),
            freshness_limit_seconds=self.max_age, automatic_resubmission=False,
            acknowledgement_timeout_seconds=ACK_TIMEOUT_SECONDS,
        )

    def _read_lifecycle(self, sample):
        if getattr(self.acq, "simulates_lifecycle", False) is not True:
            return None, ""
        try:
            cycle = sample["_observation"]["lifecycle"] if "_observation" in sample else self.acq.read_lifecycle()
            if (type(cycle) is not dict or set(cycle) != {"session_id", "revision", "quality", "state", "intent_id", "error", "phase"}
                    or cycle["session_id"] != sample["session_id"] or cycle["revision"] != sample["revision"]
                    or cycle["quality"] != "SIMULATED" or cycle["state"] not in LIFECYCLE_STATES
                    or any(not isinstance(cycle[key], str) or len(cycle[key]) > 4096 for key in ("intent_id", "error", "phase"))):
                raise ValueError("Malformed or changed ACQ lifecycle snapshot; refresh before submitting")
            return cycle, ""
        except Exception as error:
            return None, str(error)[:4096]

    def _read_setpoints(self, sample):
        if getattr(self.acq, "simulates_setpoints", False) is not True:
            return None, "Setpoint simulation not configured"
        try:
            value = sample["_observation"]["setpoints"] if "_observation" in sample else self.acq.read_setpoints()
            targets = {rule["target"] for rule in setpoint_rules()}
            if (type(value) is not dict or set(value) != {"session_id", "revision", "values", "quality"}
                    or value["session_id"] != sample["session_id"] or value["quality"] != "SIMULATED"
                    or not isinstance(value["revision"], str) or not 1 <= len(value["revision"]) <= 128
                    or type(value["values"]) is not dict or set(value["values"]) != targets):
                raise ValueError("Malformed ACQ setpoint snapshot")
            for number in value["values"].values():
                if number is not None:
                    finite_number(number)
            if value["revision"] != sample["revision"]:
                raise ValueError("ACQ changed during setpoint observation; refresh before submitting")
            return value, ""
        except Exception as error:
            return None, str(error)[:4096]

    def submit(self, intent_id, expected_revision):
        if not isinstance(expected_revision, str) or not 1 <= len(expected_revision) <= 128:
            raise ValueError("Explicit ACQ expected_revision required")
        item = self.intent(intent_id)
        if item["state"] not in ("DRAFT", "BLOCKED"):
            return item  # Repeated click cannot submit a second time, even after success.
        sample, error = self._read()
        reason = item["plan"]["blocked_reason"] or error
        is_setpoint = item["plan"]["kind"] == "SETPOINT"
        if not reason and sample:
            cycle, reason = self._read_lifecycle(sample)
            if not reason and cycle:
                procedure = item["plan"]["procedure"]
                if procedure == "acq.initialize" and cycle["state"] == "RUNNING":
                    reason = "ACQ simulation already initialized; no startup replay"
                elif procedure == "acq.stop" and cycle["state"] in ("UNMANAGED", "STOPPED"):
                    reason = "ACQ simulation not initialized or already stopped"
                elif not item["plan"].get("lifecycle") and cycle["state"] not in ("UNMANAGED", "RUNNING"):
                    reason = "ACQ lifecycle not RUNNING; explicit initialization required"
        if not reason and sample and is_setpoint:
            setpoints, reason = self._read_setpoints(sample)
            if not reason:
                current = setpoints["values"][item["plan"]["target"]]
                if current is not None and current != item["request"]["base_value"]:
                    reason = "ACQ setpoint value changed; create a new intent from current state"
        if not reason and sample:
            if sample["revision"] != expected_revision:
                reason = "ACQ revision changed; refresh before submitting"
            elif sample["run"]["state"] == "UNKNOWN" or (not is_setpoint and
                  (any(sample["dps"]) or sample["run"]["state"] in ("ACCEPTED", "RUNNING"))):
                reason = "ACQ busy; all 29 DPS fields participate in procedure gate"
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT * FROM supervision_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if current["state"] not in ("DRAFT", "BLOCKED"):
                return self._item(current)
            active_rows = db.execute("SELECT kind,state FROM supervision_intents WHERE state IN (?,?,?,?)", ACTIVE).fetchall()
            if any(row["state"] == "UNKNOWN" or not is_setpoint or row["kind"] == "SETPOINT" for row in active_rows):
                reason = "Another supervision intent has an active or unresolved outcome"
            if reason:
                self._update(db, intent_id, "BLOCKED", reason, reason)
            else:
                db.execute("UPDATE supervision_intents SET session_id=? WHERE intent_id=?", (sample["session_id"], intent_id))
                self._update(db, intent_id, "SUBMITTING", "", "Submitting once to simulated ACQ with atomic revision guard")
        if reason:
            raise BusinessBlocked(reason)
        try:
            # Port must atomically compare session/revision before accepting an intent.
            # It must reject duplicate IDs with different procedures and never raw I/O.
            if is_setpoint:
                receipt = self.acq.submit_setpoint(intent_id=intent_id, page=item["request"]["page"],
                    control=item["request"]["control"], base_value=item["request"]["base_value"],
                    expected_revision=expected_revision, session_id=sample["session_id"])
            else:
                receipt = self.acq.submit_procedure(
                    intent_id=intent_id, procedure=item["plan"]["procedure"],
                    expected_revision=expected_revision, session_id=sample["session_id"],
                )
            _validate_run(receipt)
            if (receipt["intent_id"] != intent_id or receipt["procedure"] != item["plan"]["procedure"]
                    or receipt["state"] == "IDLE"):
                raise ValueError("ACQ receipt does not acknowledge this intent")
            ack_sample = {**sample, "run": receipt}
            self._reconcile(ack_sample)
        except AcqRejected as error:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT state FROM supervision_intents WHERE intent_id=?", (intent_id,)).fetchone()
                if current["state"] == "SUBMITTING":
                    self._update(db, intent_id, "BLOCKED", str(error), "Authenticated ACQ rejection before acceptance")
            raise BusinessBlocked(str(error)) from error
        except Exception as error:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                current = db.execute("SELECT state FROM supervision_intents WHERE intent_id=?", (intent_id,)).fetchone()
                if current["state"] not in TERMINAL:
                    self._update(db, intent_id, "UNKNOWN", str(error)[:4096],
                                 "Submission outcome unknown; no automatic retry")
        return self.intent(intent_id)
