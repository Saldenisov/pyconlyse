"""Actual ORIGINAL Python 3.4 agent <-> signed TCP <-> Supervision/API; no NI calls."""
import importlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "web/backend"))
domain = importlib.import_module("elyse_supervision_business")
transport = importlib.import_module("elyse_acq_transport")
api = importlib.import_module("elyse_supervision_api")
PY34 = Path(os.environ.get(
    "ELYSE_PYTHON34", str(ROOT / "tools/xp_python34_extracted/python.exe")
))


class RemoteProcess:
    def __init__(self, directory, scale=0, fault=None, protocol="tcp"):
        if not PY34.is_file():
            pytest.skip("Actual Python 3.4 unavailable; not replaced by modern Python")
        self.path = directory / "acq.sqlite3"
        self.directory, self.protocol = directory, protocol
        self.key = uuid.uuid4().hex.encode("ascii")
        self.process = None
        self.scale, self.fault = scale, fault
        self.start()

    def start(self):
        if self.protocol != "tcp":
            raise ValueError("Integration uses only the original agent TCP listener")
        launcher = ROOT / "legacy/xp_acq_agent/main.py"
        config = self.directory / "agent.json"
        config.write_text(json.dumps(dict(mode="simulation", bind_host="127.0.0.1", command_port=8765,
                                         audit_path=str(self.directory / "audit.jsonl"),
                                         data_path=str(ROOT / "legacy/xp_acq_agent/data"))))
        extra = ["--config", str(config), "--supervision"]
        args = [str(PY34), "-u", str(launcher), *extra,
                "--bind", "127.0.0.1", "--port", "0", "--state-db", str(self.path), "--time-scale", str(self.scale)]
        if self.fault is not None:
            args += ["--simulate-failure-step", str(self.fault)]
        env = dict(os.environ, ELYSE_ACQ_SHARED_KEY=self.key.decode("ascii"))
        env.pop("ELYSE_ACQ_SHARED_KEY_FILE", None)
        self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(self.process.stdout.readline()), daemon=True)
        reader.start()
        try:
            line = ready.get(timeout=10)
            match = re.search(r"listening on 127\.0\.0\.1:(\d+);", line)
            if not match:
                self.stop()
                raise RuntimeError("Python 3.4 service failed to start")
            self.endpoint = self.protocol + "://127.0.0.1:" + match.group(1)
            self.port = transport.TcpAcqPort(self.endpoint, self.key, allow_loopback=True)
            self.port.read_state()
        except Exception:
            self.stop()
            raise

    def stop(self):
        if self.process:
            self.process.terminate()  # Only this test child, never the lab service.
            self.process.wait(timeout=10)
            self.process.stdout.close()
            self.process.stderr.close()
            self.process = None


@pytest.fixture(scope="module")
def remote(tmp_path_factory):
    instance = RemoteProcess(tmp_path_factory.mktemp("acq-py34"))
    try:
        yield instance
    finally:
        instance.stop()


@pytest.fixture
def app(remote, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    instance = Flask(__name__)
    instance.config.update(TESTING=True, JWT_SECRET_KEY="integration-test-only", ELYSE_ACQ_URL=remote.endpoint,
                           ELYSE_ACQ_SHARED_KEY=remote.key.decode("ascii"),
                           ELYSE_SUPERVISION_STATE_DB=str(tmp_path / "supervision.sqlite3"))
    JWTManager(instance)
    instance.register_blueprint(api.elyse_supervision_api)
    return instance


BUSINESS_ROOT = "/api/elyse/supervision/business"
ROUTABLE = [entry for entry in domain.catalog(simulated_plans=True) if entry["kind"] == "PROCEDURE" and not entry["blocked_reason"]]


def wait_terminal(service, intent_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = service.snapshot()
        item = service.intent(intent_id)
        if item["state"] in domain.TERMINAL:
            return item, snapshot
        time.sleep(0.02)
    raise AssertionError("No terminal acknowledgement within bounded test deadline")


@pytest.mark.parametrize("entry", ROUTABLE, ids=lambda entry: entry["procedure"])
def test_all_23_web_procedures_execute_through_actual_py34_agent(app, remote, entry):
    client = app.test_client()
    intent_id = "e2e-" + uuid.uuid4().hex
    request = dict(intent_id=intent_id, page=entry["page"], control=entry["control"])
    assert client.post(BUSINESS_ROOT + "/intents", json=request).json["intent"]["state"] == "DRAFT"
    before = client.get(BUSINESS_ROOT).json
    assert before["acq"]["quality"] == "SIMULATED"
    assert before["acq"]["endpoint"] == remote.endpoint
    response = client.post(BUSINESS_ROOT + "/intents/" + intent_id + "/submit",
                           json={"expected_revision": before["acq"]["revision"]})
    assert response.status_code == 200
    service = app.extensions["elyse_supervision_business"]
    item, snapshot = wait_terminal(service, intent_id)
    assert item["state"] == "SUCCEEDED"
    assert snapshot["execution_allowed"] is False
    assert snapshot["physical_status"] == "NOT_EXECUTED"
    trace = remote.port.trace(intent_id)
    actual = [step["operation"] for step in trace if step["step_index"] >= 0 and step["outcome"] == "SUCCEEDED"]
    from DeviceServers.control.elyse_acq.plans import get_plan
    assert actual == [step.operation.value for step in get_plan(entry["procedure"]).steps]
    restored = domain.SupervisionBusiness(service.path, remote.port)
    assert restored.submit(intent_id, before["acq"]["revision"])["state"] == "SUCCEEDED"
    assert remote.port.trace(intent_id) == trace


def test_lost_receipt_resolves_from_history_after_acq_restart(tmp_path):
    process = RemoteProcess(tmp_path)
    try:
        service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", process.port)
        service.stage(dict(intent_id="lost", page="Page Fluides", control="Marche régulation"))
        revision = process.port.read_state()["revision"]
        original = process.port.submit_procedure

        def lost_receipt(**payload):
            original(**payload)
            raise TimeoutError("Reply lost after acceptance")

        process.port.submit_procedure = lost_receipt
        assert service.submit("lost", revision)["state"] == "UNKNOWN"
        deadline = time.monotonic() + 10
        while process.port.read_intent("lost")["run"]["state"] not in domain.TERMINAL and time.monotonic() < deadline:
            time.sleep(0.02)
        assert process.port.read_intent("lost")["run"]["state"] == "SUCCEEDED"
        trace = process.port.trace("lost")
        process.stop()
        process.start()
        restored = domain.SupervisionBusiness(service.path, process.port)
        item, snapshot = wait_terminal(restored, "lost")
        assert item["state"] == "SUCCEEDED"
        assert snapshot["active_intent_id"] is None
        assert process.port.trace("lost") == trace
    finally:
        process.stop()


def test_acq_crash_retains_unknown_busy_across_both_restarts(tmp_path):
    process = RemoteProcess(tmp_path, scale=1)
    try:
        service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", process.port)
        service.stage(dict(intent_id="crash", page="Page Fluides", control="Marche régulation"))
        revision = process.port.read_state()["revision"]
        assert service.submit("crash", revision)["state"] in ("ACCEPTED", "RUNNING")
        process.stop()
        process.start()
        restored = domain.SupervisionBusiness(service.path, process.port)
        snapshot = restored.snapshot()
        assert snapshot["intents"][0]["state"] == "UNKNOWN"
        assert snapshot["submission_allowed"] is False
        assert process.port.read_state()["dps"][0] is True
        assert process.port.read_intent("crash")["run"]["state"] == "UNKNOWN"
        assert restored.submit("crash", snapshot["acq"]["revision"])["state"] == "UNKNOWN"
    finally:
        process.stop()


def test_fault_reaches_supervision_log_and_next_procedure_can_run(tmp_path):
    process = RemoteProcess(tmp_path, fault=2)
    try:
        service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", process.port)
        for intent_id in ("first-fault", "second-fault"):
            service.stage(dict(intent_id=intent_id, page="Page Fluides", control="Marche régulation"))
            service.submit(intent_id, process.port.read_state()["revision"])
            item, snapshot = wait_terminal(service, intent_id)
            assert item["state"] == "FAILED"
            assert "Injected simulation failure at step 2" in item["error"]
            assert snapshot["active_intent_id"] is None
            assert any(event["state"] == "FAILED" and event["intent_id"] == intent_id for event in snapshot["events"])
    finally:
        process.stop()


def test_atomic_revision_rejection_is_not_an_unknown_send(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    service.stage(dict(intent_id="revision-race", page="Page HT", control="Marche HT"))
    original = remote.port.submit_procedure

    def changed_at_server(**payload):
        return original(**{**payload, "expected_revision": "stale"})

    remote.port.submit_procedure = changed_at_server
    try:
        with pytest.raises(domain.BusinessBlocked, match="session/revision changed"):
            service.submit("revision-race", remote.port.read_state()["revision"])
        assert service.intent("revision-race")["state"] == "BLOCKED"
        assert service.snapshot()["active_intent_id"] is None
    finally:
        remote.port.submit_procedure = original


def test_wrong_keys_and_unsafe_endpoints_fail_closed(remote):
    wrong = transport.TcpAcqPort(remote.endpoint, b"wrong-key-with-32-bytes-at-least!!", allow_loopback=True)
    with pytest.raises(ConnectionError, match="authentication failed"):
        wrong.read_state()
    for endpoint in ("http://example.com:8768", "http://10.20.30.10", "http://user:password@10.20.30.10:8768",
                     "http://10.20.30.10:8768/other", "http://127.0.0.1:8768"):
        with pytest.raises(ValueError):
            transport.TcpAcqPort(endpoint, remote.key)


def test_bundle_is_exact_projection_of_existing_modern_models():
    from dataclasses import asdict
    from DeviceServers.control.elyse_acq.plans import PROCEDURE_PLANS
    bundle = json.loads((ROOT / "legacy/xp_acq_agent/data/supervision_procedures.json").read_text())
    assert set(bundle["plans"]) == set(PROCEDURE_PLANS)
    for name, plan in PROCEDURE_PLANS.items():
        expected = json.loads(json.dumps([dict(asdict(step), operation=step.operation.value) for step in plan.steps]))
        assert bundle["plans"][name]["steps"] == expected
        assert bundle["plans"][name]["legacy_event_case"] == plan.legacy_event_case


def test_lost_receipt_resolves_when_another_client_has_advanced_latest_run(remote, tmp_path):
    service = domain.SupervisionBusiness(tmp_path / "sup.sqlite3", remote.port)
    service.stage(dict(intent_id="history-after-other-client", page="Page Fluides", control="Marche régulation"))
    original = remote.port.submit_procedure

    def lost_receipt(**payload):
        original(**payload)
        raise TimeoutError("Reply lost after acceptance")

    remote.port.submit_procedure = lost_receipt
    try:
        assert service.submit("history-after-other-client", remote.port.read_state()["revision"])["state"] == "UNKNOWN"
    finally:
        remote.port.submit_procedure = original
    deadline = time.monotonic() + 10
    while remote.port.read_state()["run"]["state"] not in domain.TERMINAL and time.monotonic() < deadline:
        time.sleep(0.02)
    saved_trace = remote.port.trace("history-after-other-client")
    state = remote.port.read_state()
    original(intent_id="other-client", procedure="cooling.stop", expected_revision=state["revision"],
             session_id=state["session_id"])
    item, snapshot = wait_terminal(service, "history-after-other-client")
    assert item["state"] == "SUCCEEDED"
    assert snapshot["active_intent_id"] is None
    assert remote.port.read_state()["run"]["intent_id"] == "other-client"
    assert remote.port.trace("history-after-other-client") == saved_trace


def test_actual_py34_second_process_cannot_own_same_state(remote):
    env = dict(os.environ, ELYSE_ACQ_SHARED_KEY=remote.key.decode("ascii"))
    env.pop("ELYSE_ACQ_SHARED_KEY_FILE", None)
    attempted = subprocess.run([str(PY34), str(ROOT / "legacy/xp_acq_agent/main.py"),
                                "--config", str(remote.directory / "agent.json"), "--supervision",
                                "--bind", "127.0.0.1", "--port", "0", "--state-db", str(remote.path)],
                               capture_output=True, text=True, env=env, timeout=10)
    assert attempted.returncode != 0
    assert "database is locked" in attempted.stderr
    assert "listening on" not in attempted.stdout
    assert remote.port.read_state()["quality"] == "SIMULATED"
