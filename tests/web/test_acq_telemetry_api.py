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
    monkeypatch.delenv('ELYSE_TELEMETRY_ARCHIVE_CONFIG', raising=False)
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


@pytest.mark.parametrize("suffix,attribute,value,status", [
    ("/owners", "orchestrators_json", {"federated": True, "owners": {"supervision": {"quality": "WAITING"}}}, 200),
    ("/owners", "orchestrators_json", {"federated": True, "owners": {"other": {}}}, 503),
    ("/video", "video_json", {"owner": "supervision", "available": False, "frame": None}, 200),
    ("/video", "video_json", {"owner": "acquisition", "frame": {}}, 503),
])
def test_owner_and_video_reads_use_same_fixed_receiver(setup_api, monkeypatch, suffix, attribute, value, status):
    app, _, calls = setup_api
    class MetadataProxy:
        def set_timeout_millis(self, timeout):
            assert timeout == 1500
        def read_attribute(self, name):
            assert name == attribute
            return SimpleNamespace(has_failed=False, value=json.dumps(value))
    def factory(name):
        calls.append(("proxy", name))
        return MetadataProxy()
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", factory)
    response = app.test_client().get(URL + suffix)
    assert response.status_code == status
    assert calls == [("proxy", api.DEVICE)]
    if status == 200:
        assert response.json["device"] == api.TANGO_DEVICE


@pytest.mark.parametrize("suffix", ["/owners", "/video"])
def test_owner_and_video_reject_oversized_metadata(setup_api, monkeypatch, suffix):
    app, _, _ = setup_api
    class OversizedProxy:
        def set_timeout_millis(self, timeout):
            pass
        def read_attribute(self, name):
            return SimpleNamespace(value=" " * (api.MAX_JSON_BYTES + 1))
    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", lambda _: OversizedProxy())
    assert app.test_client().get(URL + suffix).status_code == 503


def test_history_is_bounded_read_only_tango_command(setup_api, monkeypatch):
    app, _, calls = setup_api
    class HistoryProxy:
        def set_timeout_millis(self, value):
            calls.append(('timeout', value))
        def command_inout(self, name, raw):
            query = json.loads(raw)
            calls.append((name, query))
            return json.dumps(dict(points=[dict(value=2**63 + 17)], complete=True))
    monkeypatch.setattr(api.tango_gateway, 'create_device_proxy', lambda name: HistoryProxy())
    response = app.test_client().get(URL + '/history', query_string=dict(
        bank='C2NI6071E', index=7, start='2026-10-22T13:45:00+02:00',
        end='2026-10-22T14:30:00+02:00', limit=500))
    assert response.status_code == 200
    assert response.json['points'][0]['value'] == {'integer_decimal': str(2**63 + 17)}
    assert calls[-1][0] == 'ReadHistory'
    assert calls[-1][1]['index'] == 7


def test_explicit_local_history_does_not_hold_tango_requests_and_failure_has_no_fallback(setup_api, monkeypatch):
    app, _, calls = setup_api
    import DeviceServers.control.elyse_acq.telemetry_archive as archive
    app.config['ELYSE_TELEMETRY_ARCHIVE_CONFIG'] = 'fixture-private-config'
    queries = []
    class Reader:
        def __init__(self, path, *, read_timeout_ms):
            assert path == 'fixture-private-config' and read_timeout_ms == 10000
        def read_history(self, query):
            queries.append(query)
            return dict(points=[dict(value=42)], complete=True)
    monkeypatch.setattr(archive, 'PostgresStore', Reader)
    query = dict(bank='EPS', index=8, start='2026-10-22T13:45:00+02:00', end='2026-10-22T14:30:00+02:00')
    response = app.test_client().get(URL + '/history', query_string=query)
    assert response.status_code == 200 and response.json['points'][0]['value'] == 42
    assert len(queries) == 1 and calls == []
    def fail(self, query):
        raise TimeoutError('fixture disk busy')
    monkeypatch.setattr(Reader, 'read_history', fail)
    assert app.test_client().get(URL + '/history', query_string=query).status_code == 503
    assert calls == []


@pytest.mark.parametrize('query', [dict(bank='unsafe', index=7), dict(bank='EPS', index=-1),
                                  dict(bank='EPS', index=1, limit=99999)])
def test_history_invalid_query_never_contacts_tango(setup_api, query):
    app, _, calls = setup_api
    response = app.test_client().get(URL + '/history', query_string=dict(
        start='2026-10-22T13:45:00+02:00', end='2026-10-22T14:30:00+02:00', **query))
    assert response.status_code == 400
    assert calls == []
    assert response.headers["Cache-Control"] == "no-store"


def test_cooling_endpoint_is_read_only_and_exposes_server_journal(setup_api):
    from legacy.xp_acq_agent.elyse_agent.cooling_safety import CoolingSafety
    app, content, calls = setup_api
    content["cooling_safety"] = CoolingSafety().snapshot()
    response = app.test_client().get(URL + "/cooling")
    assert response.status_code == 200
    assert response.json["cooling_safety"]["timeout_seconds"] == 120
    assert response.json["cooling_safety"]["automatic_stop_available"] is False
    assert calls[-1] == ("read", ["State", "telemetry_json"])
    calls.clear()
    assert app.test_client().post(URL + "/cooling", json={"reset": True}).status_code == 405
    assert calls == []


def test_read_only_receiver_cannot_claim_automatic_shutdown(setup_api):
    from legacy.xp_acq_agent.elyse_agent.cooling_safety import CoolingSafety
    app, content, _ = setup_api
    content["cooling_safety"] = CoolingSafety().snapshot()
    content["cooling_safety"]["automatic_stop_available"] = True
    assert app.test_client().get(URL + "/cooling").status_code == 503


def test_missing_cooling_service_and_unknown_source_are_explicit_not_healthy(setup_api):
    app, _, calls = setup_api
    assert app.test_client().get(URL + "/cooling").status_code == 503
    calls.clear()
    app.config["ELYSE_COOLING_SOURCE"] = "other"
    assert app.test_client().get(URL + "/cooling").status_code == 503
    assert calls == []


def test_retired_xp_runtime_source_cannot_contact_another_device(setup_api):
    app, _, calls = setup_api
    app.config["ELYSE_COOLING_SOURCE"] = "xp_runtime"
    assert app.test_client().get(URL + "/cooling").status_code == 503
    assert calls == []


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
