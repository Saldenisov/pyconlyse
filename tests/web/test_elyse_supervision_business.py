"""Supervision lifecycle tests use an explicit fake ACQ, never lab hardware."""

import importlib
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
domain = importlib.import_module("elyse_supervision_business")
api = importlib.import_module("elyse_supervision_api")
NOW = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


class FakeAcq:
    host = "10.20.30.10"
    mode = "SIMULATION"

    def __init__(self):
        self.state = dict(session_id="acq-boot-1", revision="1", quality="SIMULATED",
                          observed_at=NOW.isoformat(), dps=[False] * 29,
                          run=dict(state="IDLE", intent_id="", procedure="", error=""))
        self.calls = []
        self.failure = None
        self.entered = Event()
        self.release = None
        self.lock = Lock()

    def read_state(self):
        return deepcopy(self.state)

    def submit_procedure(self, *, intent_id, procedure, expected_revision, session_id):
        with self.lock:
            if expected_revision != self.state["revision"] or session_id != self.state["session_id"]:
                raise ValueError("Atomic ACQ revision/session conflict")
            self.calls.append(dict(intent_id=intent_id, procedure=procedure))
            self.state["run"] = dict(state="RUNNING", intent_id=intent_id, procedure=procedure, error="")
            self.state["revision"] = str(int(self.state["revision"]) + 1)
        self.entered.set()
        if self.release is not None:
            assert self.release.wait(5)
        if self.failure:
            raise self.failure
        return deepcopy(self.state["run"])


@pytest.fixture
def business(tmp_path):
    return domain.SupervisionBusiness(tmp_path / "state.sqlite3", FakeAcq(), clock=lambda: NOW)


def stage(business, intent_id="operator-1", page="Page Fluides", control="Marche régulation"):
    return business.stage(dict(intent_id=intent_id, page=page, control=control))


def test_catalog_has_23_procedures_20_arrows_and_no_arbitrary_io(business):
    entries = business.snapshot()["catalog"]
    assert len([entry for entry in entries if entry["kind"] == "PROCEDURE"]) == 23
    assert len([entry for entry in entries if entry["kind"] == "SETPOINT"]) == 20
    for entry in entries:
        stage(business, f"catalog-{entries.index(entry)}", entry["page"], entry["control"])
    assert business.acq.calls == []
    with pytest.raises(ValueError, match="Unknown page/control"):
        stage(business, page="C4", control="write digital output")


def test_default_external_host_unconfigured_never_assumes_idle(tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "state.sqlite3")
    snapshot = service.snapshot()
    assert snapshot["acq"]["host"] == "10.20.30.10"
    assert snapshot["acq"]["quality"] == "UNAVAILABLE"
    assert snapshot["submission_allowed"] is False
    assert snapshot["execution_allowed"] is False
    stage(service)
    with pytest.raises(domain.BusinessBlocked, match="not configured"):
        service.submit("operator-1", "hypothetical")
    assert service.intent("operator-1")["state"] == "BLOCKED"


def test_intent_and_event_history_survive_new_service_instance(business):
    staged = stage(business)
    restored = domain.SupervisionBusiness(business.path)
    assert restored.snapshot()["intents"][0] == staged
    assert restored.snapshot()["events"][0]["state"] == "DRAFT"
    assert business.acq.calls == []


def test_same_id_same_request_is_idempotent_different_request_conflicts(business):
    first = stage(business)
    assert stage(business) == first
    assert len(business.snapshot()["events"]) == 1
    with pytest.raises(domain.BusinessConflict):
        stage(business, control="Arrêt régulation")


@pytest.mark.parametrize("index", range(29))
def test_every_dps_bit_blocks_procedure_without_queueing(business, index):
    stage(business)
    business.acq.state["dps"][index] = True
    with pytest.raises(domain.BusinessBlocked, match="29 DPS"):
        business.submit("operator-1", "1")
    assert business.acq.calls == []
    business.acq.state["dps"][index] = False
    business.snapshot()  # Clearing busy never triggers submission.
    assert business.acq.calls == []
    assert business.submit("operator-1", "1")["state"] == "RUNNING"


@pytest.mark.parametrize("mutate", [
    lambda state: state.update(observed_at=(NOW - timedelta(seconds=6)).isoformat()),
    lambda state: state.update(observed_at=(NOW + timedelta(seconds=1)).isoformat()),
    lambda state: state.update(observed_at="2026-10-07T12:00:00"),
    lambda state: state.update(quality="GOOD"),
    lambda state: state.update(dps=[False] * 24),
    lambda state: state.update(dps=[0] * 29),
    lambda state: state.update(revision=1),
    lambda state: state.update(run={"state": "IDLE"}),
])
def test_stale_or_malformed_adapter_snapshot_fails_closed(business, mutate):
    stage(business)
    mutate(business.acq.state)
    assert business.snapshot()["submission_allowed"] is False
    with pytest.raises(domain.BusinessBlocked):
        business.submit("operator-1", "1")
    assert business.acq.calls == []


def test_wrong_host_or_production_port_cannot_dispatch(business):
    stage(business)
    business.acq.host = "127.0.0.1"
    with pytest.raises(domain.BusinessBlocked, match="host"):
        business.submit("operator-1", "1")
    business.acq.host = "10.20.30.10"
    business.acq.mode = "PRODUCTION"
    with pytest.raises(domain.BusinessBlocked, match="disabled"):
        business.submit("operator-1", "1")
    assert business.acq.calls == []


def test_changed_revision_requires_explicit_refresh(business):
    stage(business)
    business.acq.state["revision"] = "2"
    with pytest.raises(domain.BusinessBlocked, match="revision changed"):
        business.submit("operator-1", "1")
    assert business.acq.calls == []
    assert business.submit("operator-1", "2")["state"] == "RUNNING"


def test_single_flight_and_repeat_click_do_not_resubmit(business):
    stage(business)
    stage(business, "operator-2", control="Arrêt régulation")
    assert business.submit("operator-1", "1")["state"] == "RUNNING"
    assert business.submit("operator-1", "1")["state"] == "RUNNING"
    with pytest.raises(domain.BusinessBlocked):
        business.submit("operator-2", "2")
    assert len(business.acq.calls) == 1
    business.acq.state["run"]["state"] = "SUCCEEDED"
    assert business.snapshot()["active_intent_id"] is None
    assert business.submit("operator-1", "1")["state"] == "SUCCEEDED"
    assert len(business.acq.calls) == 1
    assert business.submit("operator-2", "2")["state"] == "RUNNING"


def test_concurrent_workers_and_double_click_admit_only_one_submission(business):
    stage(business)
    business.acq.release = Event()
    other = domain.SupervisionBusiness(business.path, business.acq, clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(business.submit, "operator-1", "1")
        assert business.acq.entered.wait(5)
        assert other.submit("operator-1", "1")["state"] == "SUBMITTING"
        business.acq.release.set()
        assert first.result()["state"] == "RUNNING"
    assert len(business.acq.calls) == 1


def test_lost_receipt_preserves_unknown_until_matching_ack_and_never_retries(business):
    stage(business)
    business.acq.failure = TimeoutError("Receipt lost after acceptance")
    assert business.submit("operator-1", "1")["state"] == "UNKNOWN"
    restored = domain.SupervisionBusiness(business.path, business.acq, clock=lambda: NOW)
    assert restored.submit("operator-1", "1")["state"] == "UNKNOWN"
    business.acq.state["run"]["intent_id"] = "unrelated"
    assert restored.snapshot()["active_intent_id"] == "operator-1"
    assert restored.intent("operator-1")["state"] == "UNKNOWN"
    business.acq.state["run"]["intent_id"] = "operator-1"
    business.acq.state["run"]["state"] = "FAILED"
    business.acq.state["run"]["error"] = "Cooling timeout"
    assert restored.snapshot()["intents"][0]["state"] == "FAILED"
    assert restored.intent("operator-1")["error"] == "Cooling timeout"
    assert len(business.acq.calls) == 1


def test_acq_restart_cannot_acknowledge_previous_session(business):
    stage(business)
    business.submit("operator-1", "1")
    business.acq.state["session_id"] = "acq-boot-2"
    business.acq.state["run"]["state"] = "SUCCEEDED"
    snapshot = business.snapshot()
    assert snapshot["intents"][0]["state"] == "UNKNOWN"
    assert snapshot["submission_allowed"] is False
    assert "session changed" in snapshot["intents"][0]["error"]


def test_worker_crash_before_dispatch_becomes_unknown_after_deadline(business):
    stage(business)
    # Simulate a process dying after the durable admission, before remote I/O.
    with business._db() as db:
        db.execute("UPDATE supervision_intents SET state='SUBMITTING',session_id='acq-boot-1'")
    later = NOW + timedelta(seconds=16)
    business.acq.state["observed_at"] = later.isoformat()
    restored = domain.SupervisionBusiness(business.path, business.acq, clock=lambda: later)
    snapshot = restored.snapshot()
    assert snapshot["intents"][0]["state"] == "UNKNOWN"
    assert snapshot["submission_allowed"] is False
    assert restored.submit("operator-1", "1")["state"] == "UNKNOWN"
    assert business.acq.calls == []


def test_old_active_intent_is_not_hidden_by_recent_drafts(business):
    stage(business)
    business.submit("operator-1", "1")
    for index in range(55):
        stage(business, f"draft-{index}")
    snapshot = business.snapshot()
    assert snapshot["active_intent_id"] == "operator-1"
    assert snapshot["intents"][0]["intent_id"] == "operator-1"
    assert len(snapshot["intents"]) == 51


@pytest.mark.parametrize("state", domain.TERMINAL)
def test_terminal_ack_is_not_physical_readback_and_dps_can_still_block(business, state):
    stage(business)
    business.submit("operator-1", "1")
    business.acq.state["run"]["state"] = state
    business.acq.state["dps"][28] = True
    snapshot = business.snapshot()
    assert snapshot["intents"][0]["state"] == state
    assert snapshot["submission_allowed"] is False
    assert snapshot["physical_status"] == "NOT_EXECUTED"
    assert snapshot["execution_allowed"] is False


@pytest.mark.parametrize("page,control,reason", [
    ("Page Alimentations", "Marche Aimants.", "ownership"),
    ("Page Alimentations", "Arrêt Aimants", "ownership"),
    ("Page Alimentations", "Aimant 0V", "ownership"),
    ("Page HT", "> HT", "setpoint API"),
])
def test_uncommissioned_magnet_and_setpoint_routes_stay_blocked(business, page, control, reason):
    stage(business, page=page, control=control)
    with pytest.raises(domain.BusinessBlocked, match=reason):
        business.submit("operator-1", "1")
    assert business.acq.calls == []


@pytest.fixture
def app(business, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    instance = Flask(__name__)
    instance.config.update(TESTING=True, JWT_SECRET_KEY="business-test-only")
    JWTManager(instance)
    instance.extensions["elyse_supervision_business"] = business
    instance.register_blueprint(api.elyse_supervision_api)
    return instance


ROOT = "/api/elyse/supervision/business"


def test_http_stage_submit_restore_and_no_store(app):
    client = app.test_client()
    payload = dict(intent_id="http-1", page="Page HT", control="Marche HT")
    assert client.post(f"{ROOT}/intents", json=payload).json["intent"]["state"] == "DRAFT"
    snapshot = client.get(ROOT)
    assert snapshot.headers["Cache-Control"] == "no-store"
    assert snapshot.json["intents"][0]["request"] == payload
    assert client.post(f"{ROOT}/intents/http-1/submit", json={"expected_revision": "1"}).json["intent"]["state"] == "RUNNING"
    assert client.get(ROOT).json["active_intent_id"] == "http-1"


@pytest.mark.parametrize("payload", [
    '{"intent_id":"x","intent_id":"y","page":"Page HT","control":"Marche HT"}',
    '{"intent_id":"x","page":"Page HT","control":"Marche HT","dps":[false]}',
    '{"intent_id":"x","page":"Page HT","control":"Marche HT","value":NaN}',
    '[]',
])
def test_http_rejects_duplicate_keys_telemetry_injection_and_nonfinite(app, payload):
    assert app.test_client().post(f"{ROOT}/intents", data=payload, content_type="application/json").status_code == 400


def test_http_idempotency_conflict_blocked_unknown_and_size(app):
    client = app.test_client()
    payload = dict(intent_id="http-1", page="Page HT", control="Marche HT")
    client.post(f"{ROOT}/intents", json=payload)
    assert client.post(f"{ROOT}/intents", json={**payload, "control": "Arrêt HT"}).status_code == 409
    assert client.post(f"{ROOT}/intents/http-1/submit", json={"expected_revision": "old"}).status_code == 409
    assert client.post(f"{ROOT}/intents/missing/submit", json={"expected_revision": "1"}).status_code == 404
    assert client.post(f"{ROOT}/intents", data=" " * 65537, content_type="application/json").status_code == 400


@pytest.mark.parametrize("method,path", [("get", ROOT), ("post", f"{ROOT}/intents"), ("post", f"{ROOT}/intents/x/submit"),
                                        ("get", f"{ROOT}/intents/x/trace")])
def test_business_auth_guard_covers_reads_and_mutations(app, monkeypatch, method, path):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    assert getattr(app.test_client(), method)(path).status_code == 401
