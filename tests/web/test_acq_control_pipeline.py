"""Real authenticated loopback HTTP, real broker/owner, fake NI and Tango only."""
import json
import threading
import time
from types import SimpleNamespace
from uuid import uuid4

from tests.web.test_acq_control_api import api, ROOT
from tests.unit.test_acq_control_release import normal_sample
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

from legacy.xp_acq_control.elyse_agent.acquisition_control_runtime import AcquisitionControlRuntime, control_identity
from legacy.xp_acq_control.elyse_agent.acquisition_remote import ControlHTTPServer
from legacy.xp_acq_control.elyse_agent.acquisition_recovery import OwnershipMarker
from DeviceServers.control.elyse_acq.control_client import ControlClient, ControlBridge
from DeviceServers.control.elyse_acq.control_runtime_health import INPUT_BANKS


def test_web_tango_http_owner_general_water_next_stage_and_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    effects = []
    class FakeCards:
        resource_count = 0
        control_profile = "extended_ht_stop"
        ht_feedback_verified = stage_controls_verified = ht_controls_verified = focal_controls_verified = True
        counter_controls_verified = True
        focal_command = SimpleNamespace(resources_verified=True)
        procedure = None
        def initialize(self, cancel, startup_confirmed=False):
            assert startup_confirmed
            self.resource_count = 1
            effects.append(("initialize-fake-cards", threading.get_ident()))
        def general_start(self, cancel, operator_confirmed=False):
            assert operator_confirmed
            effects.append(("general", threading.get_ident()))
        def execute_stage(self, operation, cancel, operator_confirmed=False):
            assert operator_confirmed
            effects.append((operation, threading.get_ident()))
        def general_stop(self, operator_confirmed=False):
            assert operator_confirmed
            effects.append(("general.stop", threading.get_ident()))
        def read_snapshot(self, cancel):
            sample = normal_sample()
            for name, (kind, device, size) in INPUT_BANKS.items():
                bank = sample["banks"].setdefault(name, dict(values=[False if kind == "digital_input" else 0.] * size))
                bank.update(kind=kind, device=device)
                if kind == "analog_input": bank["legacy_scaled_values"] = list(bank["values"])
            return sample
        def close(self):
            effects.append(("close-fake-cards", threading.get_ident()))
            self.resource_count = 0
    identity = control_identity()
    guard = OwnershipMarker(str(tmp_path / "fake.ownership"), identity["session_id"], identity["build_id"])
    runtime = AcquisitionControlRuntime(FakeCards, remote_enabled=True, cooling_polarity_verified=True,
                                        identity=identity, recovery_guard=guard, period=.02)
    server = ControlHTTPServer(("127.0.0.1", 0), runtime, b"r" * 32, b"w" * 32)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.02), daemon=True)
    bridge = ControlBridge(ControlClient(b"r" * 32, b"w" * 32, enabled=True,
                                         host="127.0.0.1", port=server.server_port))
    class FakeTango:
        def set_timeout_millis(self, value): pass
        def read_attribute(self, name):
            bridge.poll_once()
            return SimpleNamespace(has_failed=False, value=json.dumps(bridge.snapshot()))
        def command_inout(self, name, encoded):
            assert name == "ExecuteCommand"
            return json.dumps(bridge.client.submit(json.loads(encoded)))
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", lambda device: FakeTango() if device == api.DEVICE else None)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-pipeline-secret-000000000000000",
                      ELYSE_CONTROL_STATE_DB=str(tmp_path / "web.sqlite3"), ELYSE_ACQUISITION_SOURCE="xp_control")
    JWTManager(app); app.register_blueprint(api.api)
    with app.app_context(): token = create_access_token(identity="test-operator")
    client, headers = app.test_client(), {"Authorization": "Bearer " + token}
    def until(predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.02)
        raise AssertionError("fake owner did not reach expected state: " + str(runtime.snapshot()))
    def submit(operation):
        state = client.get(ROOT).json
        return client.post(ROOT + "/commands", json=dict(command_id=uuid4().hex, session_id=state["session_id"],
            expected_revision=state["revision"], operation=operation, operator_confirmed=True, value=None), headers=headers)
    runtime.start(); worker.start()
    try:
        assert client.get(ROOT).json["execution_allowed"] is False
        assert effects == []  # HTTP availability does not initialize cards.
        runtime.initialize(startup_confirmed=True)
        until(lambda: runtime.snapshot()["state"] == "RUNNING" and not runtime.snapshot()["stale"])
        started = submit("modulator.general.start")
        assert started.json["receipt"]["outcome"] == "QUEUED", started.json
        until(lambda: runtime.snapshot()["general_cooling_ready"] is True and runtime.snapshot()["state"] == "RUNNING")
        assert [name for name, unused in effects][:3] == ["initialize-fake-cards", "general", "cooling.start"]
        until(lambda: not runtime.snapshot()["stale"])
        assert submit("modulator.general.start").status_code == 409
        heated = submit("chauffage.start")
        assert heated.json["receipt"]["outcome"] == "QUEUED", heated.json
        until(lambda: runtime.snapshot()["state"] == "RUNNING" and not runtime.snapshot()["stale"])
        stopped = submit("modulator.general.stop")
        assert stopped.json["receipt"]["outcome"] == "QUEUED", stopped.json
        until(lambda: not runtime.snapshot()["general_stop_required"] and runtime.snapshot()["state"] == "RUNNING")
        view = client.get(ROOT).json
        assert view["commands"][0]["outcome"] == "COMPLETED"
        assert view["commands"][0]["hardware_acknowledged"] is False
        runtime.request_shutdown(); assert runtime.join(3)
        assert len({owner for unused, owner in effects}) == 1
        assert [name for name, unused in effects][-3:] == ["chauffage.start", "general.stop", "close-fake-cards"]
    finally:
        runtime.request_shutdown(electrical_off_confirmed=True)
        runtime.join(3)
        server.shutdown(); server.server_close(); worker.join(2)
