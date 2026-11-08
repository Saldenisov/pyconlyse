"""Web -> original Python 3.4 agent -> logical setpoint, no physical hardware."""
import json
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

import test_elyse_acq_process_integration as integration
from test_elyse_acq_tcp_integration import legacy
from legacy.xp_acq_agent.elyse_agent.supervision_setpoints import rules, adjusted

domain = integration.domain
app = integration.app
remote = integration.remote
ROOT = integration.BUSINESS_ROOT


@pytest.mark.parametrize("rule", rules(), ids=lambda rule: rule["procedure"])
def test_all_twenty_arrows_are_submitted_via_flask_to_actual_py34(app, remote, rule):
    client = app.test_client()
    observed = client.get(ROOT).json
    entry = next(entry for entry in observed["catalog"] if entry["page"] == rule["page"] and entry["control"] == rule["control"])
    assert entry["blocked_reason"] == ""
    current = observed["acq"]["setpoints"][rule["target"]]
    base = current if current is not None else 10
    intent_id = "arrow-" + uuid.uuid4().hex
    request = dict(intent_id=intent_id, page=rule["page"], control=rule["control"], base_value=base)
    staged = client.post(ROOT + "/intents", json=request)
    assert staged.status_code == 200
    assert staged.json["intent"]["plan"]["requested_value"] == adjusted(rule, base)
    assert staged.json["intent"]["state"] == "DRAFT"
    revision = client.get(ROOT).json["acq"]["revision"]
    submitted = client.post(ROOT + "/intents/" + intent_id + "/submit", json=dict(expected_revision=revision))
    assert submitted.status_code == 200
    assert submitted.json["intent"]["state"] == "SUCCEEDED"
    assert remote.port.outputs()["analog"][rule["target"]] == adjusted(rule, base)
    trace = remote.port.trace(intent_id)
    assert trace[-1]["detail"]["value"] == adjusted(rule, base)
    assert trace[-1]["detail"]["target"] == rule["target"]
    selected_trace = client.get(ROOT + "/intents/" + intent_id + "/trace")
    assert selected_trace.status_code == 200
    assert selected_trace.json["intent_id"] == intent_id
    assert selected_trace.json["phases"] == trace
    snapshot = legacy(remote, "get_snapshot")["result"]
    assert snapshot["procedure_outputs"]["analog"][rule["target"]] == adjusted(rule, base)
    assert snapshot["procedure_output_units"] == "LEGACY_LOGICAL_SIMULATION"
    restored = domain.SupervisionBusiness(app.config["ELYSE_SUPERVISION_STATE_DB"], remote.port)
    assert restored.snapshot()["acq"]["setpoints"][rule["target"]] == adjusted(rule, base)
    assert restored.intent(intent_id)["state"] == "SUCCEEDED"
    assert restored.submit(intent_id, "obsolete")["state"] == "SUCCEEDED"
    assert remote.port.trace(intent_id) == trace


def stage(service, remote, intent_id="arrow", base=None):
    current = remote.port.read_setpoints()["values"]["C8NI6703.01"]
    base = (current if current is not None else 20) if base is None else base
    return service.stage(dict(intent_id=intent_id, page="Page Fluides", control="> Canon", base_value=base))


def test_arrow_overlaps_running_procedure_without_replacing_its_acknowledgement(tmp_path):
    remote = integration.RemoteProcess(tmp_path, scale=1)
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    try:
        service.stage(dict(intent_id="procedure", page="Page Fluides", control="Marche régulation"))
        service.submit("procedure", remote.port.read_state()["revision"])
        before = remote.port.read_state()
        assert before["run"]["state"] in ("ACCEPTED", "RUNNING")
        stage(service, remote)
        snapshot = service.snapshot()
        assert snapshot["busy"] is True
        assert snapshot["submission_allowed"] is False
        assert snapshot["setpoint_submission_allowed"] is True
        assert service.submit("arrow", snapshot["acq"]["revision"])["state"] == "SUCCEEDED"
        after = remote.port.read_state()
        assert after["run"]["intent_id"] == "procedure"
        assert after["dps"] == before["dps"]
        assert service.intent("procedure")["state"] in ("ACCEPTED", "RUNNING")
        # The test owns this process; completing all 15-second waits is unnecessary.
    finally:
        remote.stop()


def test_stale_base_cannot_overwrite_another_clients_value(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    item = stage(service, remote, "stale")
    stage(service, remote, "other")
    service.submit("other", remote.port.read_state()["revision"])
    previous = remote.port.outputs()
    with pytest.raises(domain.BusinessBlocked, match="value changed"):
        service.submit("stale", remote.port.read_state()["revision"])
    assert remote.port.outputs() == previous
    assert service.intent("stale")["request"] == item["request"]


def test_lost_setpoint_receipt_resolves_from_history_after_both_restarts(tmp_path):
    remote = integration.RemoteProcess(tmp_path)
    original = remote.port.submit_setpoint
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    try:
        stage(service, remote)
        def lost(**payload):
            original(**payload)
            raise ConnectionError("Injected lost acknowledgement")
        remote.port.submit_setpoint = lost
        assert service.submit("arrow", remote.port.read_state()["revision"])["state"] == "UNKNOWN"
        before = remote.port.outputs()
        trace = remote.port.trace("arrow")
        remote.stop()
        remote.start()
        restored = domain.SupervisionBusiness(service.path, remote.port)
        snapshot = restored.snapshot()
        assert restored.intent("arrow")["state"] == "SUCCEEDED"
        assert snapshot["busy"] is False
        assert remote.port.outputs() == before
        assert remote.port.trace("arrow") == trace
        assert restored.submit("arrow", "obsolete")["state"] == "SUCCEEDED"
    finally:
        remote.stop()


def test_unknown_setpoint_blocks_procedures_and_other_arrows_without_resending(tmp_path):
    remote = integration.RemoteProcess(tmp_path)
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    try:
        stage(service, remote)
        service.submit("arrow", remote.port.read_state()["revision"])
        remote.stop()
        # Durable acceptance marker emulates loss between acceptance and terminal commit.
        with sqlite3.connect(remote.path) as db:
            db.execute("UPDATE setpoint_intents SET state='ACCEPTED' WHERE intent_id='arrow'")
        with sqlite3.connect(service.path) as db:
            db.execute("UPDATE supervision_intents SET state='UNKNOWN' WHERE intent_id='arrow'")
        remote.start()
        restored = domain.SupervisionBusiness(service.path, remote.port)
        snapshot = restored.snapshot()
        assert restored.intent("arrow")["state"] == "UNKNOWN"
        assert snapshot["submission_allowed"] is False
        assert snapshot["setpoint_submission_allowed"] is False
        stage(restored, remote, "new-arrow")
        restored.stage(dict(intent_id="new-procedure", page="Page Fluides", control="Marche régulation"))
        for intent in ("new-arrow", "new-procedure"):
            with pytest.raises(domain.BusinessBlocked):
                restored.submit(intent, remote.port.read_state()["revision"])
        trace = remote.port.trace("arrow")
        assert restored.submit("arrow", "obsolete")["state"] == "UNKNOWN"
        assert remote.port.trace("arrow") == trace
    finally:
        remote.stop()


def test_faulted_stub_reports_failure_without_mutation_then_new_intent_recovers(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    previous = remote.port.outputs()
    try:
        legacy(remote, "set_simulation_scenario", dict(name="fault"))
        stage(service, remote, "faulted-arrow")
        assert service.submit("faulted-arrow", remote.port.read_state()["revision"])["state"] == "FAILED"
        assert remote.port.outputs() == previous
        assert "Simulated equipment fault" in service.intent("faulted-arrow")["error"]
        legacy(remote, "set_simulation_scenario", dict(name="idle"))
        stage(service, remote, "recovered-arrow")
        assert service.submit("recovered-arrow", remote.port.read_state()["revision"])["state"] == "SUCCEEDED"
    finally:
        legacy(remote, "set_simulation_scenario", dict(name="idle"))


def test_concurrent_snapshot_readers_and_setpoint_writers_never_deadlock(remote):
    def snapshots():
        for unused in range(25):
            assert legacy(remote, "get_snapshot")["ok"] is True
    def writes():
        for unused in range(25):
            state = remote.port.read_setpoints()
            current = state["values"]["C8NI6703.01"]
            assert remote.port.submit_setpoint(intent_id="parallel-" + uuid.uuid4().hex,
                page="Page Fluides", control="> Canon", base_value=current if current is not None else 20,
                expected_revision=state["revision"], session_id=state["session_id"])["state"] == "SUCCEEDED"
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(snapshots), pool.submit(snapshots), pool.submit(writes)]
        for job in jobs:
            job.result(timeout=15)


@pytest.mark.parametrize("number", [True, "20", None, float('nan'), float('inf'), -float('inf')])
def test_flask_rejects_untyped_base_before_dispatch(app, number):
    response = app.test_client().post(ROOT + "/intents", json=dict(intent_id="bad", page="Page Fluides", control="> Canon", base_value=number))
    assert response.status_code == 400


@pytest.mark.parametrize("base", [-1e4, 0, 10, 1e4])
@pytest.mark.parametrize("rule", rules(), ids=lambda rule: rule["procedure"])
def test_portable_arithmetic_matches_independent_recovered_event_model(rule, base):
    native = domain.model("parameter_page_events")
    page = native.ParameterPage(rule["page"])
    planned = native.plan_parameter_page_change(page,
        {name: True for name in native.DPS_FIELDS},
        {item.arrow: item.arrow == rule["control"] for item in native.PARAMETER_RULES if item.page == page},
        {name: False for name, unused in native.PROCEDURE_FIELD_MAPS[page]},
        {rule["numeric_field"]: base})
    assert planned.projected_numeric == adjusted(rule, base)


def test_old_sqlite_schema_is_migrated_without_losing_intents_or_exclusion(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript("""CREATE TABLE supervision_intents (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,intent_id TEXT UNIQUE NOT NULL,
            request_json TEXT NOT NULL,plan_json TEXT NOT NULL,state TEXT NOT NULL,error TEXT NOT NULL DEFAULT '',
            session_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE UNIQUE INDEX supervision_single_flight ON supervision_intents ((1))
              WHERE state IN ('SUBMITTING','ACCEPTED','RUNNING','UNKNOWN');""")
        plan = next(entry for entry in domain.catalog() if entry["control"] == "Marche régulation")
        db.execute("INSERT INTO supervision_intents VALUES (NULL,?,?,?,?,?,?,?,?)", ("old", '{}', json.dumps(plan),
                   "UNKNOWN", "Lost", "boot", "2026-10-07T12:00:00Z", "2026-10-07T12:00:00Z"))
    service = domain.SupervisionBusiness(path)
    assert service.intent("old")["state"] == "UNKNOWN"
    assert service.snapshot()["busy"] is True
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT kind FROM supervision_intents WHERE intent_id='old'").fetchone()[0] == "PROCEDURE"
