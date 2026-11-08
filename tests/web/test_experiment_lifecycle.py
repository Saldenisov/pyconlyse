"""Persistence and polling never replay a preparation command."""

import time
from threading import Event
from types import SimpleNamespace

from flask import Flask
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from experiment_lifecycle import ExperimentLifecycle, ProgressSteps


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    instance = ExperimentLifecycle(tmp_path / "lifecycle.sqlite3")
    monkeypatch.setattr(api, "_lifecycle_instance", instance)
    return instance


@pytest.fixture
def client(lifecycle):
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    return app.test_client()


def test_refresh_and_duplicate_start_attach_to_one_worker(client, lifecycle, monkeypatch):
    entered, finish, released = Event(), Event(), Event()
    calls = []

    def prepare(steps):
        calls.append("prepare")
        steps.append({"step": "SD2 PDU", "status": "verified"})
        steps.phase("Waiting for Kymera power", wait_until=time.time() + 30)
        entered.set()
        assert finish.wait(3)
        return {"steps": list(steps), "already_ready": True, "message": "Already running"}

    monkeypatch.setattr(api, "_initialize_experiment", prepare)
    try:
        first = client.post("/api/pump-probe-vd2/initialize?background=1")
        assert first.status_code == 202
        assert entered.wait(2)
        for _ in range(3):
            saved = client.get("/api/pump-probe-vd2/lifecycle").get_json()["job"]
            assert saved["job_id"] == first.get_json()["job"]["job_id"]
            assert saved["phase"] == "Waiting for Kymera power"
            assert saved["steps"] == [{"step": "SD2 PDU", "status": "verified"}]
            assert 29 <= saved["wait_until"] - saved["server_time"] <= 30
        duplicate = client.post("/api/pump-probe-vd2/initialize?background=1")
        assert duplicate.status_code == 202
        assert duplicate.get_json()["attached"] is True
        assert calls == ["prepare"]
        assert client.post("/api/pump-probe-vd2/deinitialize?background=1").status_code == 409
        assert client.post("/api/pump-probe-vd2/protocol/start", json={}).status_code == 409
    finally:
        finish.set()
        # A bounded wait observes lock release without starting hardware.
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if api._preparation_lock.acquire(False):
                api._preparation_lock.release()
                released.set()
                break
            time.sleep(0.01)
        assert released.is_set()
    assert lifecycle.snapshot()["status"] == "completed"
    restarted = ExperimentLifecycle(lifecycle.path)
    assert restarted.snapshot()["result"]["already_ready"] is True


def test_server_restart_retains_progress_but_marks_interrupted(lifecycle):
    lifecycle.put("job", {"status": "running", "steps": [{"step": "PDU", "status": "ON"}],
                           "wait_until": time.time() + 30, "operation": "prepare"})
    lifecycle.put("camera_power_wait", {"pending": True, "deadline": 12345})
    restarted = ExperimentLifecycle(lifecycle.path)
    assert restarted.snapshot()["status"] == "interrupted"
    assert restarted.snapshot()["steps"] == [{"step": "PDU", "status": "ON"}]
    assert restarted.get("camera_power_wait")["deadline"] == 12345
    assert "never replayed" in restarted.snapshot()["error"]


def test_failure_persists_partial_checks_and_releases_lock(client, lifecycle, monkeypatch):
    def fail(steps):
        steps.append({"step": "PDU", "status": "ON"})
        raise api.PreparationFailure("OWIS connection timed out", steps)
    monkeypatch.setattr(api, "_initialize_experiment", fail)
    assert client.post("/api/pump-probe-vd2/initialize?background=1").status_code == 202
    deadline = time.monotonic() + 2
    while lifecycle.snapshot()["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert lifecycle.snapshot()["status"] == "failed"
    assert lifecycle.snapshot()["error"] == "OWIS connection timed out"
    assert lifecycle.snapshot()["steps"] == [{"step": "PDU", "status": "ON"}]


@pytest.mark.parametrize("route", ["initialize", "deinitialize"])
def test_background_mutations_preserve_exact_authorization_guard(client, lifecycle, monkeypatch, route):
    monkeypatch.setattr(api, "authorization_required", lambda: True)
    monkeypatch.setattr(lifecycle, "start", lambda *_args: pytest.fail("No worker without authorization"))
    result = client.post(f"/api/pump-probe-vd2/{route}?background=1")
    assert result.status_code == 403


class PDU:
    def __init__(self, states):
        self.states = states
        self.writes = []

    def read_attribute(self, name):
        return SimpleNamespace(value=[3, 1, 4, 2] if name == "ids" else self.states)

    def command_inout(self, name, values):
        assert name == "set_channels_states"
        self.writes.append(values)
        self.states = values


def test_cold_camera_power_wait_is_durable_and_precedes_instrument_start(lifecycle, monkeypatch):
    lifecycle.put("job", {"status": "running"})
    pdu = PDU([1, 0, 0, 1])
    steps = ProgressSteps(lifecycle)
    events = []
    monkeypatch.setattr(api.time, "time", lambda: 1000)

    def wait(seconds):
        events.append(("wait", seconds))
        saved = lifecycle.snapshot()
        assert saved["wait_until"] == 1030
        assert "before server initialization" in saved["phase"]
        assert lifecycle.get("camera_power_wait")["pending"] is True

    monkeypatch.setattr(api.time, "sleep", wait)
    monkeypatch.setattr(api, "_assert_preparation_idle", lambda: None)
    monkeypatch.setattr(api, "_prepared_equipment_state", lambda: None)
    def ensure(device, _steps):
        events.append(("ensure", device))
        if device == api.DG645_DEVICE:
            raise RuntimeError("Stop the fake flow after the wait")
        return pdu
    monkeypatch.setattr(api, "_ensure_server", ensure)
    with pytest.raises(RuntimeError, match="Stop the fake"):
        api._initialize_equipment(steps)
    assert ("wait", 30) in events
    assert events.index(("wait", 30)) < events.index(("ensure", api.DG645_DEVICE))
    assert lifecycle.get("camera_power_wait")["pending"] is False


@pytest.mark.parametrize("states,expected", [([1, 1, 0, 1], []), ([1, 1, 0, 0], [2.0])])
def test_already_powered_camera_does_not_repeat_30_second_delay(states, expected, monkeypatch):
    sleeps = []
    monkeypatch.setattr(api.time, "sleep", sleeps.append)
    api._enable_vd2_power(PDU(states), [])
    assert sleeps == expected


@pytest.mark.parametrize("previous,seconds", [({"pending": True, "deadline": 1017}, 17),
                                             ({"pending": True, "deadline": None}, 30)])
def test_retry_honors_interrupted_power_wait(lifecycle, monkeypatch, previous, seconds):
    lifecycle.put("job", {"status": "running"})
    lifecycle.put("camera_power_wait", previous)
    monkeypatch.setattr(api.time, "time", lambda: 1000)
    sleeps = []
    monkeypatch.setattr(api.time, "sleep", sleeps.append)
    api._enable_vd2_power(PDU([1, 1, 0, 1]), ProgressSteps(lifecycle))
    assert sleeps == [seconds]


def test_malformed_power_readback_never_reaches_instrument_wait(monkeypatch):
    pdu = PDU([1, 0, 0, 1])
    def read(name):
        if name == "ids":
            return SimpleNamespace(value=[1, 1, 2, 3])
        return SimpleNamespace(value=pdu.states)
    monkeypatch.setattr(pdu, "read_attribute", read)
    monkeypatch.setattr(api.time, "sleep", lambda *_args: pytest.fail("No wait/start on invalid power"))
    with pytest.raises(RuntimeError, match="IDs and states"):
        api._enable_vd2_power(pdu, [])
    assert not pdu.writes


def test_power_loss_during_settling_prevents_instrument_initialization(lifecycle, monkeypatch):
    lifecycle.put("job", {"status": "running"})
    pdu = PDU([1, 0, 0, 1])
    def lose_power(_seconds):
        pdu.states[1] = 0
    monkeypatch.setattr(api.time, "sleep", lose_power)
    with pytest.raises(RuntimeError, match="no instrument initialization attempted"):
        api._enable_vd2_power(pdu, ProgressSteps(lifecycle))
    assert lifecycle.get("camera_power_wait") == {"pending": True, "deadline": None}


def test_power_intent_is_committed_before_uncertain_pdu_write(lifecycle, monkeypatch):
    lifecycle.put("job", {"status": "running"})
    pdu = PDU([1, 0, 0, 1])
    def timeout(*_args):
        assert lifecycle.get("camera_power_wait") == {"pending": True, "deadline": None}
        raise RuntimeError("PDU reply lost")
    monkeypatch.setattr(pdu, "command_inout", timeout)
    with pytest.raises(RuntimeError, match="PDU reply lost"):
        api._enable_vd2_power(pdu, ProgressSteps(lifecycle))


def test_event_history_retains_previous_jobs_and_supports_read_only_pagination(client, lifecycle):
    for index in range(110):
        lifecycle.record({"job_id": f"job-{index // 55}", "status": "completed", "operation": "prepare"},
                         {"kind": "progress", "message": f"event-{index}"})
    restored = ExperimentLifecycle(lifecycle.path)
    current = restored.snapshot()
    assert current["job_id"] == "job-1"
    assert len(current["events"]) == 100
    previous = client.get(f'/api/pump-probe-vd2/lifecycle/log?before={current["events"][0]["id"]}').get_json()["events"]
    assert len(previous) == 10
    assert previous[0]["message"] == "event-0"
    assert current["events"][-1]["message"] == "event-109"
    assert restored.get("job") == lifecycle.get("job")
    assert client.get('/api/pump-probe-vd2/lifecycle/log?before=invalid').status_code == 400


def test_async_repeat_records_verified_readiness_without_a_false_failure(client, lifecycle, monkeypatch):
    def repeat(steps):
        raise api.AlreadyPrepared({"steps": [{"step": "DG645", "status": "verified BURM = 0"}]})
    monkeypatch.setattr(api, "_initialize_experiment", repeat)
    assert client.post('/api/pump-probe-vd2/initialize?background=1').status_code == 202
    deadline = time.monotonic() + 2
    while lifecycle.snapshot()["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    restored = ExperimentLifecycle(lifecycle.path).snapshot()
    assert restored["status"] == "completed"
    assert restored["error"] == ""
    assert restored["result"]["already_ready"] is True
    assert restored["steps"] == [{"step": "DG645", "status": "verified BURM = 0"}]
    assert "already switched on" in restored["result"]["message"]
    assert restored["events"][-1]["kind"] == "completed"
    assert client.get('/api/pump-probe-vd2/lifecycle').get_json()["job"]["result"]["already_ready"] is True
