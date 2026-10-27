"""Independent SuperVision read facade: no bank fallback, commands or XP calls."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("acq_telemetry_api")
URL = "/api/elyse/acquisition/telemetry/synchronization"


def counter(**changes):
    value = dict(owner="supervision", available=True, stale=False, values=list(range(16)),
        age_seconds=.2, session_id="a" * 32, sequence=12, source_mode="LABVIEW_BRIDGE",
        source="observed_labview_control_memory", selector=-1, pending_selector=False,
        source_identity=None, read_only=True, hardware_acknowledged=False,
        physical_measurements_verified=False)
    value.update(changes)
    return value


@pytest.fixture
def facade(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="counter-read-test-secret")
    JWTManager(app)
    app.register_blueprint(api.acq_telemetry_api)
    calls = []
    state = dict(raw=json.dumps(counter()), failed=False)
    class Proxy:
        def set_timeout_millis(self, timeout):
            calls.append(("timeout", timeout))
        def read_attribute(self, name):
            calls.append(("attribute", name))
            return SimpleNamespace(has_failed=state["failed"], value=state["raw"])
    def factory(device):
        calls.append(("device", device))
        return Proxy()
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    return app, state, calls


def test_fixed_independent_counter_read_and_all16_values(facade):
    app, _, calls = facade
    response = app.test_client().get(URL + "?device=unsafe&bank=C1011NI6602")
    assert response.status_code == 200
    assert response.json["values"] == list(range(16))
    assert response.json["source_host"] == "10.20.30.2"
    assert response.json["read_only"] is True
    assert response.json["hardware_acknowledged"] is False
    assert calls == [("device", api.DEVICE), ("timeout", 1500), ("attribute", "supervision_counter_json")]
    assert response.headers["Cache-Control"] == "no-store"


def test_stale_values_hidden_without_fallback_to_legacy_bank(facade):
    app, state, calls = facade
    state["raw"] = json.dumps(counter(age_seconds=2.1))
    response = app.test_client().get(URL)
    assert response.status_code == 200 and response.json["values"] is None
    assert response.json["stale"] is True
    assert len(calls) == 3


@pytest.mark.parametrize("patch", [dict(owner="acquisition"), dict(values=[1] * 15),
    dict(values=[True] * 16), dict(values=[float("nan")] * 16), dict(hardware_acknowledged=True),
    dict(physical_measurements_verified=True), dict(read_only=False), dict(session_id="bad"),
    dict(source="last_successful_counter_command_memory"), dict(selector=3, pending_selector=False)])
def test_invalid_or_foreign_observation_fails_closed(facade, patch):
    app, state, _ = facade
    state["raw"] = json.dumps(counter(**patch))
    response = app.test_client().get(URL)
    assert response.status_code == 503 and response.json["values"] is None


@pytest.mark.parametrize("raw", ['{"owner":"supervision","owner":"acquisition"}',
                                 '{"value": Infinity}', " " * (api.MAX_JSON_BYTES + 1)],
                         ids=["duplicate", "nonfinite", "oversized"])
def test_counter_uses_active_strict_bounded_observer_parser(facade, raw):
    app, state, _ = facade
    state["raw"] = raw
    assert app.test_client().get(URL).status_code == 503


def test_failed_attribute_and_unconfigured_ds_are_distinct(facade):
    app, state, _ = facade
    state["failed"] = True
    assert app.test_client().get(URL).status_code == 503
    state.update(failed=False, raw=json.dumps(dict(owner="supervision", available=False,
        values=None, read_only=True, hardware_acknowledged=False,
        reason="SUPERVISION_COUNTER_NOT_CONFIGURED")))
    response = app.test_client().get(URL)
    assert response.status_code == 200 and response.json["available"] is False


def test_protected_counter_read_requires_authentication(monkeypatch, facade):
    app, _, calls = facade
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    assert app.test_client().get(URL).status_code == 401
    assert calls == []
