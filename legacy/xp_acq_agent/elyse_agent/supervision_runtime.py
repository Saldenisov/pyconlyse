"""Durable single-flight, named-procedure simulation for Python 3.4/XP.

Imports no NI/Tango/serial driver. Output images are logical simulation values,
not calibrated voltages or hardware readback. No hardware activation option.
"""
from __future__ import print_function

import copy
import datetime
import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager

from .supervision_wire import strict_json
from .supervision_setpoints import rules as setpoint_rules, finite_number, adjusted
from . import supervision_lifecycle as lifecycle

TERMINAL = ("SUCCEEDED", "FAILED", "CANCELLED")
ACTIVE = ("ACCEPTED", "RUNNING", "UNKNOWN")


def utc_now():
    return datetime.datetime.utcnow().isoformat() + "Z"


class Rejected(ValueError):
    """Definite rejection before acceptance, never an ambiguous I/O failure."""


class SimulationCancelled(RuntimeError):
    pass


def load_plans(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "supervision_procedures.json")
    with open(path, "rb") as stream:
        bundle = strict_json(stream.read())
    if bundle.get("schema_version") != 1 or bundle.get("simulation_only") is not True:
        raise ValueError("Simulation-only procedure bundle required")
    plans = bundle["plans"]
    if len(plans) != 23 or set(p["legacy_event_case"] for p in plans.values()) != set(range(3, 26)):
        raise ValueError("Expected all 23 reviewed procedure cases")
    return plans


class MemoryOutputs(object):
    def __init__(self, image=None):
        self._lock = threading.RLock()
        self.image = copy.deepcopy(image or dict(digital={}, analog={}, counters={}, focal_supplies_enabled=False))

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self.image)

    def execute(self, step, wait):
        operation = step["operation"]
        if operation.startswith("lifecycle_"):
            return lifecycle.execute(self, step, wait)
        targets = step["targets"]
        value = step["value"]
        if operation == "wait":
            wait(step["duration_s"])
            return {"seconds": step["duration_s"]}
        if operation == "analog_sweep":
            metadata = step["metadata"]
            current = float(metadata["initial"])
            for unused in range(metadata["iterations"]):
                current += metadata["delta"]
                with self._lock:
                    for target in targets:
                        self.image["analog"][target] = current
                wait(metadata["period_s"])
        else:
            with self._lock:
                if operation in ("write_digital", "write_digital_group"):
                    for target in targets:
                        self.image["digital"][target] = bool(value)
                elif operation == "write_analog_group":
                    for target in targets:
                        self.image["analog"][target] = float(value)
                elif operation == "set_focal_supplies":
                    self.image["focal_supplies_enabled"] = bool(value)
                elif operation == "start_counters":
                    for target in targets:
                        self.image["counters"][target] = "RUNNING"
                elif operation == "stop_counter_when_done":
                    self.image["counters"][targets[0]] = "STOPPED"
                else:
                    raise ValueError("Unknown simulation operation: {0}".format(operation))
        return {"targets": targets, "value": value, "simulated": True}


class SupervisionRuntime(object):
    def __init__(self, path, time_scale=1.0, step_hook=None, simulate_all_plans=False, simulate_setpoints=False, simulate_lifecycle=False):
        if isinstance(time_scale, bool) or not math.isfinite(float(time_scale)) or not 0 <= float(time_scale) <= 1:
            raise ValueError("Simulation time_scale must be in 0..1")
        self.path = os.path.abspath(path)
        parent = os.path.dirname(self.path)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        self.plans = load_plans()
        if type(simulate_all_plans) is not bool:
            raise ValueError("Explicit Boolean simulation-plan opt-in required")
        self.simulate_all_plans = simulate_all_plans
        if type(simulate_setpoints) is not bool:
            raise ValueError("Explicit Boolean setpoint-simulation opt-in required")
        self.simulate_setpoints = simulate_setpoints
        self.setpoint_rules = setpoint_rules()
        if type(simulate_lifecycle) is not bool:
            raise ValueError("Explicit Boolean lifecycle-simulation opt-in required")
        self.simulate_lifecycle = simulate_lifecycle
        if simulate_lifecycle:
            self.plans.update(lifecycle.plans())
        self.session_id = uuid.uuid4().hex
        self.time_scale = float(time_scale)
        self.step_hook = step_hook  # Local fault injection only, never an HTTP parameter.
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._worker = None
        self._closed = False
        self._owner = sqlite3.connect(self.path + ".owner", timeout=0)
        try:
            # Separate ownership database holds a process-lifetime SQLite lock.
            # Released by the OS on a crash; never recover by deleting lock files.
            self._owner.execute("CREATE TABLE IF NOT EXISTS owner (slot INTEGER PRIMARY KEY)")
            # Python 3.4 sqlite3 commits before DDL. Acquire AFTER CREATE, then
            # keep a DML transaction open; otherwise the lifetime lock is lost.
            self._owner.execute("BEGIN EXCLUSIVE")
            self._owner.execute("INSERT OR IGNORE INTO owner(slot) VALUES (1)")
            with self._db() as db:
                db.executescript("""
                    CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY,value TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS intents (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,intent_id TEXT UNIQUE NOT NULL,
                        procedure TEXT NOT NULL,session_id TEXT NOT NULL,state TEXT NOT NULL,
                        error TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS active (slot INTEGER PRIMARY KEY,intent_id TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS events (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,intent_id TEXT NOT NULL,
                        step_index INTEGER NOT NULL,operation TEXT NOT NULL,outcome TEXT NOT NULL,
                        detail TEXT NOT NULL,recorded_at TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS setpoint_intents (
                        seq INTEGER PRIMARY KEY AUTOINCREMENT,intent_id TEXT UNIQUE NOT NULL,
                        procedure TEXT NOT NULL,request_json TEXT NOT NULL,session_id TEXT NOT NULL,
                        state TEXT NOT NULL,error TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
                """)
                self._set_default(db, "revision", "0")
                self._set_default(db, "dps", json.dumps([False] * 29))
                self._set_default(db, "image", json.dumps(MemoryOutputs().image))
                # Existing procedure-only state is retained, never silently reset.
                self._set_default(db, "lifecycle", json.dumps(dict(state="UNMANAGED", intent_id="", error="", phase="")))
                active = db.execute("SELECT intent_id FROM active").fetchone()
                if active:
                    self._set_run(db, active["intent_id"], "UNKNOWN", "ACQ restarted with unresolved accepted intent")
                    self._event(db, active["intent_id"], -1, "recovery", "UNKNOWN", {})
                    cycle = json.loads(self._meta(db, "lifecycle"))
                    if cycle["state"] in ("INITIALIZING", "STOPPING"):
                        cycle.update(state="UNKNOWN", error="ACQ restarted during lifecycle; no automatic replay")
                        self._put(db, "lifecycle", json.dumps(cycle))
                for row in db.execute("SELECT intent_id FROM setpoint_intents WHERE state IN ('ACCEPTED','RUNNING')").fetchall():
                    db.execute("UPDATE setpoint_intents SET state='UNKNOWN',error=?,updated_at=? WHERE intent_id=?",
                               ("ACQ restarted with unresolved setpoint intent", utc_now(), row["intent_id"]))
                    self._event(db, row["intent_id"], -1, "recovery", "UNKNOWN", {})
                self.outputs = MemoryOutputs(json.loads(self._meta(db, "image")))
                self._bump(db)
        except Exception:
            self._owner.close()
            raise

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _set_default(db, name, value):
        db.execute("INSERT OR IGNORE INTO meta(name,value) VALUES (?,?)", (name, value))

    @staticmethod
    def _meta(db, name):
        return db.execute("SELECT value FROM meta WHERE name=?", (name,)).fetchone()["value"]

    @staticmethod
    def _put(db, name, value):
        db.execute("UPDATE meta SET value=? WHERE name=?", (value, name))

    def _bump(self, db):
        self._put(db, "revision", str(int(self._meta(db, "revision")) + 1))

    @staticmethod
    def _run(row):
        return dict((name, row[name]) for name in ("state", "intent_id", "procedure", "error"))

    @staticmethod
    def _set_run(db, intent_id, state, error=""):
        db.execute("UPDATE intents SET state=?,error=?,updated_at=? WHERE intent_id=?",
                   (state, error, utc_now(), intent_id))

    @staticmethod
    def _event(db, intent_id, index, operation, outcome, detail):
        db.execute("INSERT INTO events(intent_id,step_index,operation,outcome,detail,recorded_at) VALUES (?,?,?,?,?,?)",
                   (intent_id, index, operation, outcome, json.dumps(detail, allow_nan=False), utc_now()))

    def read_state(self):
        with self._lock, self._db() as db:
            row = db.execute("SELECT i.* FROM intents i JOIN active a ON i.intent_id=a.intent_id").fetchone()
            if row is None:
                row = db.execute("SELECT * FROM setpoint_intents WHERE state='UNKNOWN' ORDER BY seq LIMIT 1").fetchone()
            if row is None:
                row = db.execute("SELECT * FROM intents ORDER BY seq DESC LIMIT 1").fetchone()
            run = self._run(row) if row else dict(state="IDLE", intent_id="", procedure="", error="")
            return dict(session_id=self.session_id, revision=self._meta(db, "revision"),
                        observed_at=utc_now(), quality="SIMULATED",
                        dps=json.loads(self._meta(db, "dps")), run=run)

    def read_intent(self, intent_id):
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
            if row is None:
                row = db.execute("SELECT * FROM setpoint_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if row is None:
                raise KeyError("Unknown ACQ intent")
            return dict(session_id=row["session_id"], run=self._run(row))

    def read_lifecycle(self):
        if not self.simulate_lifecycle:
            raise Rejected("Lifecycle simulation not enabled")
        with self._lock, self._db() as db:
            return dict(session_id=self.session_id, revision=self._meta(db, "revision"),
                        quality="SIMULATED", **json.loads(self._meta(db, "lifecycle")))

    def read_observation(self):
        # One signed read: no revision/phase/value mixture across TCP requests.
        with self._lock, self.outputs._lock:
            return dict(state=self.read_state(),
                        lifecycle=self.read_lifecycle() if self.simulate_lifecycle else None,
                        setpoints=self.read_setpoints() if self.simulate_setpoints else None)

    def trace(self, intent_id):
        self.read_intent(intent_id)
        with self._db() as db:
            return [dict(step_index=row["step_index"], operation=row["operation"],
                         outcome=row["outcome"], detail=json.loads(row["detail"]), recorded_at=row["recorded_at"])
                    for row in db.execute("SELECT * FROM events WHERE intent_id=? ORDER BY seq", (intent_id,))]

    def submit_procedure(self, intent_id, procedure, expected_revision, session_id):
        # Retain the lock across durable admission and worker startup/close.
        with self._lock:
            return self._submit_locked(intent_id, procedure, expected_revision, session_id)

    def _submit_locked(self, intent_id, procedure, expected_revision, session_id):
        if not isinstance(intent_id, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}\Z", intent_id):
            raise Rejected("Invalid intent_id")
        if not isinstance(procedure, str) or procedure not in self.plans:
            raise Rejected("Unknown procedure; raw I/O and orphan PT are not accepted")
        plan = self.plans[procedure]
        if plan["blocked_reason"] and not self.simulate_all_plans:
            raise Rejected(plan["blocked_reason"])
        with self._lock, self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM intents WHERE intent_id=?", (intent_id,)).fetchone()
            if db.execute("SELECT 1 FROM setpoint_intents WHERE intent_id=?", (intent_id,)).fetchone():
                raise Rejected("intent_id reused for a setpoint")
            if prior:
                if prior["procedure"] != procedure:
                    raise Rejected("intent_id reused with different procedure")
                return self._run(prior)  # Durable deduplication before revision/busy checks.
            if self._closed:
                raise Rejected("ACQ server is closing")
            if session_id != self.session_id or expected_revision != self._meta(db, "revision"):
                raise Rejected("ACQ session/revision changed")
            if (db.execute("SELECT 1 FROM active").fetchone() or any(json.loads(self._meta(db, "dps")))
                    or db.execute("SELECT 1 FROM setpoint_intents WHERE state IN ('ACCEPTED','RUNNING','UNKNOWN')").fetchone()):
                raise Rejected("ACQ busy; all 29 DPS fields participate in procedure gate")
            cycle = json.loads(self._meta(db, "lifecycle"))
            if plan.get("kind") == "LIFECYCLE":
                if procedure == "acq.initialize" and cycle["state"] == "RUNNING":
                    raise Rejected("ACQ simulation already initialized; no startup replay")
                if procedure == "acq.stop" and cycle["state"] in ("UNMANAGED", "STOPPED"):
                    raise Rejected("ACQ simulation not initialized or already stopped")
                cycle.update(state="INITIALIZING" if procedure == "acq.initialize" else "STOPPING",
                             intent_id=intent_id, error="", phase="admission")
                self._put(db, "lifecycle", json.dumps(cycle))
            elif self.simulate_lifecycle and cycle["state"] not in ("UNMANAGED", "RUNNING"):
                raise Rejected("ACQ lifecycle not RUNNING; explicit initialization required")
            now = utc_now()
            db.execute("INSERT INTO intents(intent_id,procedure,session_id,state,error,created_at,updated_at) VALUES (?,?,?,'ACCEPTED','',?,?)",
                       (intent_id, procedure, self.session_id, now, now))
            db.execute("INSERT INTO active(slot,intent_id) VALUES (1,?)", (intent_id,))
            dps = json.loads(self._meta(db, "dps"))
            if plan["dps_index"] is not None:
                dps[plan["dps_index"]] = True
            self._put(db, "dps", json.dumps(dps))
            self._event(db, intent_id, -1, "admission", "ACCEPTED", {"procedure": procedure})
            self._bump(db)
        receipt = dict(state="ACCEPTED", intent_id=intent_id, procedure=procedure, error="")
        with self._lock:
            self._cancel.clear()
            self._worker = threading.Thread(target=self._execute, args=(intent_id, plan), name="acq-sim-procedure")
            self._worker.daemon = True
            try:
                self._worker.start()
            except Exception as error:
                self._finish(intent_id, plan, "FAILED", str(error))
                return self.read_intent(intent_id)["run"]
        return receipt

    def read_setpoints(self):
        if not self.simulate_setpoints:
            raise Rejected("Setpoint simulation not enabled")
        with self._lock, self.outputs._lock, self._db() as db:
            return dict(session_id=self.session_id, revision=self._meta(db, "revision"),
                        values=dict((rule["target"], self.outputs.image["analog"].get(rule["target"]))
                                    for rule in self.setpoint_rules), quality="SIMULATED")

    def submit_setpoint(self, intent_id, page, control, base_value, expected_revision, session_id):
        if not self.simulate_setpoints:
            raise Rejected("Setpoint simulation not enabled")
        if not isinstance(intent_id, str) or not re.match(r"^[A-Za-z0-9_-]{1,128}\Z", intent_id):
            raise Rejected("Invalid intent_id")
        rule = next((rule for rule in self.setpoint_rules
                     if rule["page"] == page and rule["control"] == control), None)
        if rule is None:
            raise Rejected("Unknown named setpoint; raw I/O forbidden")
        base_value = finite_number(base_value)
        value = adjusted(rule, base_value)
        canonical = json.dumps(dict(page=page, control=control, base_value=base_value), sort_keys=True, ensure_ascii=False)
        with self._lock, self._db() as db:
            prior = db.execute("SELECT * FROM setpoint_intents WHERE intent_id=?", (intent_id,)).fetchone()
            if prior:
                if prior["request_json"] != canonical:
                    raise Rejected("intent_id reused with different setpoint request")
                return self._run(prior)
        # Backend snapshots take backend -> runtime locks. Never call backend
        # readiness while holding runtime/image locks (inverse order deadlocks).
        readiness_failure = None
        try:
            if self.step_hook:
                self.step_hook(0, dict(operation="setpoint", label=control, targets=[rule["target"]], value=value))
        except Exception as failure:
            readiness_failure = failure
        # Native arrows may run during a procedure. Serialize only the atomic
        # simulated compare/write, never wait for procedure completion or clear DPS.
        with self._lock, self.outputs._lock:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM intents WHERE intent_id=?", (intent_id,)).fetchone():
                    raise Rejected("intent_id reused for a procedure")
                prior = db.execute("SELECT * FROM setpoint_intents WHERE intent_id=?", (intent_id,)).fetchone()
                if prior:
                    if prior["request_json"] != canonical:
                        raise Rejected("intent_id reused with different setpoint request")
                    return self._run(prior)
                if self._closed:
                    raise Rejected("ACQ server is closing")
                if session_id != self.session_id or expected_revision != self._meta(db, "revision"):
                    raise Rejected("ACQ session/revision changed")
                if (db.execute("SELECT 1 FROM intents WHERE state='UNKNOWN'").fetchone()
                        or db.execute("SELECT 1 FROM setpoint_intents WHERE state IN ('ACCEPTED','RUNNING','UNKNOWN')").fetchone()):
                    raise Rejected("ACQ unresolved outcome; no new setpoint")
                cycle = json.loads(self._meta(db, "lifecycle"))
                if self.simulate_lifecycle and cycle["state"] not in ("UNMANAGED", "RUNNING"):
                    raise Rejected("ACQ lifecycle excludes setpoints during initialization/stop or fault")
                current = self.outputs.image["analog"].get(rule["target"])
                if current is not None and current != base_value:
                    raise Rejected("ACQ setpoint value changed; refresh before submitting")
                now = utc_now()
                db.execute("INSERT INTO setpoint_intents VALUES (NULL,?,?,?,?, 'ACCEPTED','',?,?)",
                           (intent_id, rule["procedure"], canonical, self.session_id, now, now))
                self._event(db, intent_id, -1, "admission", "ACCEPTED", dict(page=page, control=control))
                self._bump(db)
            state, error = "SUCCEEDED", ""
            detail = dict(page=page, control=control, target=rule["target"], base_value=base_value,
                          value=value, seeded=current is None, simulated=True, native_limits=rule["native_limits"])
            try:
                if readiness_failure is not None:
                    raise readiness_failure
                # Successful image and terminal acknowledgement commit together.
                with self._db() as db:
                    next_image = self.outputs.snapshot()
                    next_image["analog"][rule["target"]] = value
                    self._put(db, "image", json.dumps(next_image, allow_nan=False))
                    db.execute("UPDATE setpoint_intents SET state='SUCCEEDED',updated_at=? WHERE intent_id=?", (utc_now(), intent_id))
                    self._event(db, intent_id, 0, "setpoint", "SUCCEEDED", detail)
                    self._bump(db)
                self.outputs.image = next_image
            except Exception as failure:
                state, error = "FAILED", "{0}: {1}".format(type(failure).__name__, failure)
                with self._db() as db:
                    db.execute("UPDATE setpoint_intents SET state=?,error=?,updated_at=? WHERE intent_id=?",
                               (state, error, utc_now(), intent_id))
                    self._event(db, intent_id, 0, "setpoint", state, dict(error=error))
                    self._bump(db)
            return dict(state=state, intent_id=intent_id, procedure=rule["procedure"], error=error)

    def _wait(self, seconds):
        remaining = float(seconds) * self.time_scale
        while remaining > 0:
            interval = min(remaining, 0.05)
            if self._cancel.wait(interval):
                raise SimulationCancelled("Simulation stopped; not hardware shutdown")
            remaining -= interval
        if self._cancel.is_set():
            raise SimulationCancelled("Simulation stopped; not hardware shutdown")

    def _execute(self, intent_id, plan):
        state, error = "SUCCEEDED", ""
        failures = []
        is_lifecycle = plan.get("kind") == "LIFECYCLE"
        try:
            with self._lock, self._db() as db:
                self._set_run(db, intent_id, "RUNNING")
                self._bump(db)
            for index, step in enumerate(plan["steps"]):
                self._wait(0)
                with self._lock, self._db() as db:
                    self._event(db, intent_id, index, step["operation"], "STARTED", {"label": step["label"]})
                    if is_lifecycle:
                        cycle = json.loads(self._meta(db, "lifecycle"))
                        cycle["phase"] = step["label"]
                        self._put(db, "lifecycle", json.dumps(cycle))
                try:
                    if self.step_hook:
                        self.step_hook(index, copy.deepcopy(step))
                    detail = self.outputs.execute(step, self._wait)
                except SimulationCancelled:
                    raise
                except Exception as failure:
                    message = "{0}: {1}".format(type(failure).__name__, failure)
                    with self._lock, self._db() as db:
                        self._put(db, "image", json.dumps(self.outputs.snapshot(), allow_nan=False))
                        self._event(db, intent_id, index, step["operation"], "FAILED", dict(label=step["label"], error=message))
                        self._bump(db)
                    if plan["name"] != "acq.stop":
                        raise
                    # Best-effort SIMULATED stop: independently attempt every
                    # remaining effect/close, but never claim STOPPED on failure.
                    failures.append(step["label"] + ": " + message)
                    continue
                with self._lock, self._db() as db:
                    self._put(db, "image", json.dumps(self.outputs.snapshot(), allow_nan=False))
                    self._event(db, intent_id, index, step["operation"], "SUCCEEDED", detail)
                    if is_lifecycle and "lifecycle_dps" in self.outputs.image:
                        self._put(db, "dps", json.dumps(self.outputs.image["lifecycle_dps"]))
                    self._bump(db)
            if failures:
                state, error = "FAILED", "; ".join(failures)[:4000]
        except SimulationCancelled as failure:
            state, error = "CANCELLED", str(failure)
        except Exception as failure:
            state, error = "FAILED", "{0}: {1}".format(type(failure).__name__, failure)
        self._finish(intent_id, plan, state, error)

    def _finish(self, intent_id, plan, state, error):
        with self._lock, self._db() as db:
            # Preserve partial simulated actuator changes even on failure/cancel.
            self._put(db, "image", json.dumps(self.outputs.snapshot(), allow_nan=False))
            self._set_run(db, intent_id, state, error)
            self._event(db, intent_id, -1, "completion", state, {"error": error})
            dps = json.loads(self._meta(db, "dps"))
            if plan["dps_index"] is not None:
                dps[plan["dps_index"]] = False  # Do not clear unrelated requests.
            if plan.get("kind") == "LIFECYCLE":
                cycle = json.loads(self._meta(db, "lifecycle"))
                cycle.update(state=("RUNNING" if plan["name"] == "acq.initialize" else "STOPPED")
                             if state == "SUCCEEDED" else "FAULT", error=error, phase="completion")
                self._put(db, "lifecycle", json.dumps(cycle))
            self._put(db, "dps", json.dumps(dps))
            db.execute("DELETE FROM active WHERE intent_id=?", (intent_id,))
            self._bump(db)

    def close(self):
        with self._lock:
            self._closed = True
            self._cancel.set()
            worker = self._worker
        if worker:
            worker.join(2)
            if worker.is_alive():
                raise RuntimeError("Simulation worker did not stop; ownership lock retained")
        if self._owner:
            self._owner.rollback()
            self._owner.close()
            self._owner = None
