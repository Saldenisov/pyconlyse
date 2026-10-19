"""Telemetry HTTP reads only a fake fixed Tango receiver; no hardware/network."""

import importlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
api = importlib.import_module("acq_telemetry_api")
URL = "/api/elyse/acquisition/telemetry"


def snapshot():
    return dict(
        source="copied_labview_telemetry",
        hardware_writes=False,
        storage_mode="ram_latest",
        receiver_session="receiver-1",
        received_this_process=12,
        duplicate_receipts=0,
        history_available=False,
        physical_measurements_verified=False,
        publications={
            name: dict(
                data=[1.5, False],
                lv_type={"type": "LvVariant"},
                error=dict(status=False, code=0, source=""),
                age_seconds=0.2,
                stale=False,
                sequence=18,
            )
            for name in api.BANKS
        },
    )


@pytest.fixture
def setup_api(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY="test-only-telemetry-read-secret")
    JWTManager(app)
    app.register_blueprint(api.acq_telemetry_api)
    calls = []
    content = snapshot()

    class Proxy:
        def set_timeout_millis(self, timeout):
            calls.append(("timeout", timeout))

        def read_attributes(self, names):
            calls.append(("read", names))
            return [
                SimpleNamespace(has_failed=False, value="ON"),
                SimpleNamespace(has_failed=False, value=json.dumps(content)),
            ]

    def factory(name):
        calls.append(("proxy", name))
        return Proxy()

    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    return app, content, calls


def test_fixed_receiver_read_no_write_or_device_selection(setup_api):
    app, _, calls = setup_api
    response = app.test_client().get(URL + "?device=other/device/unsafe")
    data = response.json
    assert response.status_code == 200
    assert calls == [
        ("proxy", api.DEVICE),
        ("timeout", 1500),
        ("read", ["State", "telemetry_json"]),
    ]
    assert data["quality"] == "FRESH"
    assert len(data["snapshot"]["publications"]) == 27
    assert data["execution_allowed"] is False and data["hardware_writes"] is False
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_no_mutation_route(setup_api, method):
    app, _, calls = setup_api
    assert (
        getattr(app.test_client(), method)(URL, json={"command": "Start"}).status_code
        == 405
    )
    assert calls == []


def test_receiver_on_does_not_mean_fresh_values(setup_api):
    app, content, _ = setup_api
    content["publications"][api.BANKS[0]]["age_seconds"] = 2.01
    data = app.test_client().get(URL).json
    assert data["server_state"] == "ON" and data["quality"] == "STALE"
    assert data["stale_banks"] == [api.BANKS[0]]


def test_empty_receiver_reset_does_not_reuse_values(setup_api):
    app, content, _ = setup_api
    client = app.test_client()
    assert client.get(URL).json["quality"] == "FRESH"
    content.update(
        receiver_session="receiver-2", received_this_process=0, publications={}
    )
    data = client.get(URL).json
    assert data["quality"] == "WAITING"
    assert data["snapshot"]["publications"] == {}
    assert len(data["missing_banks"]) == 27


def test_incomplete_and_failed_read_are_not_fresh(setup_api):
    app, content, _ = setup_api
    content["publications"].pop(api.BANKS[-1])
    assert app.test_client().get(URL).json["quality"] == "INCOMPLETE"
    content["publications"][api.BANKS[0]]["error"] = dict(
        status=True, code=42, source="control missing"
    )
    data = app.test_client().get(URL).json
    assert data["quality"] == "READ_ERROR"
    assert data["error_banks"] == [api.BANKS[0]]


def test_nonfinite_and_large_integer_preserved_without_rounding(setup_api):
    app, content, _ = setup_api
    content["publications"][api.BANKS[0]]["data"] = [
        False,
        0,
        {"nonfinite": "NaN"},
        2**63 - 1,
    ]
    value = (
        app.test_client()
        .get(URL)
        .json["snapshot"]["publications"][api.BANKS[0]]["data"]
    )
    assert value == [
        False,
        0,
        {"nonfinite": "NaN"},
        {"integer_decimal": "9223372036854775807"},
    ]


@pytest.mark.parametrize("defect", ["age", "unknown_bank", "hardware", "nan"])
def test_corrupt_receiver_rejected(setup_api, defect):
    app, content, _ = setup_api
    bank = content["publications"][api.BANKS[0]]
    if defect == "age":
        bank["age_seconds"] = -1
    elif defect == "unknown_bank":
        content["publications"]["UNEXPECTED"] = deepcopy(bank)
    elif defect == "hardware":
        content["hardware_writes"] = True
    else:
        bank["data"] = [float("nan")]
    response = app.test_client().get(URL)
    assert response.status_code == 503
    assert response.json["quality"] == "UNAVAILABLE"
    assert "snapshot" not in response.json


def test_offline_returns_503_no_fallback(setup_api, monkeypatch):
    app, _, calls = setup_api

    def fail(_):
        raise RuntimeError("offline")

    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", fail)
    response = app.test_client().get(URL)
    assert response.status_code == 503
    assert calls == []


def test_production_read_requires_existing_jwt_before_tango_access(
    setup_api, monkeypatch
):
    app, _, calls = setup_api
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    client = app.test_client()
    assert client.get(URL).status_code == 401
    assert calls == []
    with app.app_context():
        token = create_access_token(identity="operator")
    assert (
        client.get(URL, headers={"Authorization": "Bearer " + token}).status_code == 200
    )
