import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from tests._tango_stub import install_tango_stub


class CollectionPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value


install_tango_stub(CollectionPatch())
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
import pump_probe_vd2_api as vd2
from vd2_alignment_presets import AlignmentSnapshots, CHANNELS, DEVICE


def channels():
    return [dict(id=slot, name=name, value=1, measured=1, min=-15, max=15, state=1)
            for slot, name in zip([1, 3, 5, 6, 7, 9, 11, 12], CHANNELS)]


def payload(**extra):
    return dict(device=DEVICE, kind="manual_best", expected=channels(), operation_id=str(uuid.uuid4()), **extra)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(vd2, "_alignment_snapshots", lambda: AlignmentSnapshots(tmp_path / "db"))
    monkeypatch.setattr(vd2, "_alignment_current_snapshot", channels)
    monkeypatch.setattr(vd2, "_lifecycle", lambda: pytest.fail("preset access must not construct/recover lifecycle"))
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    return app.test_client()


def test_list_is_database_only_and_saved_currents_survive_next_request(client, monkeypatch):
    monkeypatch.setattr(vd2, "DeviceProxy", lambda *args: pytest.fail("listing must not reach hardware"))
    assert client.get("/api/pump-probe-vd2/alignment/snapshots").json["recommended"] is None
    saved = client.post("/api/pump-probe-vd2/alignment/snapshots", json=payload())
    assert saved.status_code == 201
    data = client.get("/api/pump-probe-vd2/alignment/snapshots").json
    assert data["best"] == saved.json["snapshot"]
    assert data["best"]["channels"][1]["id"] == 3


def test_idempotent_retry_does_not_read_hardware_again(client, monkeypatch):
    request = payload()
    first = client.post("/api/pump-probe-vd2/alignment/snapshots", json=request)
    monkeypatch.setattr(vd2, "_alignment_current_snapshot", lambda: pytest.fail("replay reread hardware"))
    repeated = client.post("/api/pump-probe-vd2/alignment/snapshots", json=request)
    assert repeated.status_code == 200
    assert repeated.json == first.json
    request["context"] = {"different": True}
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=request).status_code == 409


def test_db_failure_or_missing_parent_precedes_native_reads(client, monkeypatch, tmp_path):
    monkeypatch.setattr(vd2, "_alignment_current_snapshot", lambda: pytest.fail("must persist before native access"))
    request = payload()
    request.update(kind="before_restore", parent_id="not-found")
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=request).status_code == 409
    monkeypatch.setattr(vd2, "_alignment_snapshots", lambda: AlignmentSnapshots(tmp_path))
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=payload()).status_code == 503


@pytest.mark.parametrize("data", ["null", "{}", '{"device":"x","device":"y"}', '{"value":NaN}'])
def test_malformed_requests_never_reach_native(client, monkeypatch, data):
    monkeypatch.setattr(vd2, "_alignment_current_snapshot", lambda: pytest.fail("invalid request reached native"))
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", data=data, content_type="application/json").status_code == 400


def test_changed_readback_or_off_output_does_not_create_best(client, monkeypatch):
    values = channels()
    values[-1]["state"] = 0
    monkeypatch.setattr(vd2, "_alignment_current_snapshot", lambda: values)
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=payload()).status_code == 409
    values[-1]["state"] = 1
    values[-1]["value"] = 2
    values[-1]["measured"] = 2
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=payload()).status_code == 409
    assert client.get("/api/pump-probe-vd2/alignment/snapshots").json["history"] == []


@pytest.mark.parametrize("callable_failed", [False, True])
def test_native_reader_only_reads_fixed_attributes_and_handles_pytango_failure_property(monkeypatch, callable_failed):
    values = channels()
    data = dict(names=list(CHANNELS), ids=[c["id"] for c in values], states=[1]*8,
                currents_setpoint=[1]*8, currents_meas=[1]*8, current_limits=[-15, 15]*8)
    class Proxy:
        def set_timeout_millis(self, value):
            assert value == 5000
        def read_attributes(self, names):
            assert set(names) == set(data)
            return [SimpleNamespace(value=data[name], has_failed=(lambda: False) if callable_failed else False) for name in names]
        def command_inout(self, *args):
            pytest.fail("snapshot reader issued a hardware command")
    def proxy(device):
        assert device == DEVICE
        return Proxy()
    monkeypatch.setattr(vd2, "DeviceProxy", proxy)
    assert vd2._alignment_current_snapshot() == values


def test_auth_failure_precedes_db_and_native(client, monkeypatch):
    import mutation_auth
    from flask_jwt_extended.exceptions import JWTExtendedException
    monkeypatch.setattr(mutation_auth, "mutation_auth_required", lambda: True)
    def deny():
        raise JWTExtendedException("No login")
    monkeypatch.setattr(mutation_auth, "verify_jwt_in_request", deny)
    monkeypatch.setattr(vd2, "_alignment_snapshots", lambda: pytest.fail("unauthenticated DB access"))
    assert client.post("/api/pump-probe-vd2/alignment/snapshots", json=payload()).status_code == 401
