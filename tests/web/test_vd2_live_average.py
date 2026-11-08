import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify
from tests._tango_stub import install_tango_stub

class CollectionPatch:
    def setitem(self, mapping, key, value):
        mapping[key] = value
install_tango_stub(CollectionPatch())
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))
import pump_probe_vd2_api as vd2


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    return app.test_client()


class Proxy:
    def __init__(self, status="idle", mismatch=False):
        self.values = {"RecurFilter2": "0", "RecurNumber2": "2"}
        self.writes = []
        self.status = status
        self.mismatch = mismatch

    def command_inout(self, command, query):
        assert command == "ExecuteRaw"
        if query == "AcqStatus()":
            return "0,AcqStatus," + self.status
        name, args = query[:-1].split("(", 1)
        parts = args.split(",")
        assert parts[0] == "Live" and parts[1] in self.values
        if name == "CamParamSet":
            self.writes.append(query)
            if not self.mismatch:
                self.values[parts[1]] = parts[2]
            return "0,CamParamSet"
        assert name == "CamParamGet"
        return "0,CamParamGet," + self.values[parts[1]]


def test_get_reads_software_rolling_average_without_writes(client, monkeypatch):
    proxy = Proxy()
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    response = client.get("/api/pump-probe-vd2/live/rolling-average")
    assert response.json == {"success": True, "enabled": False, "frames": 2}
    assert proxy.writes == []


@pytest.mark.parametrize("status", ["idle", "busy,Live"])
def test_apply_verifies_live_number_before_enabling_filter(client, monkeypatch, status):
    proxy = Proxy(status)
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    response = client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": 10})
    assert response.json == {"success": True, "enabled": True, "frames": 10}
    assert proxy.writes == ["CamParamSet(Live,RecurNumber2,10)", "CamParamSet(Live,RecurFilter2,1)"]


def test_denial_precedes_proxy_and_binds_exact_live_commands(client, monkeypatch):
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("hardware before authorization"))
    plans = []
    def deny(**plan):
        plans.append(plan)
        return jsonify({"success": False}), 428
    monkeypatch.setattr(vd2, "require_http_hardware", deny)
    response = client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": 10})
    assert response.status_code == 428
    assert plans[0]["args"]["commands"] == ["CamParamSet(Live,RecurNumber2,10)", "CamParamSet(Live,RecurFilter2,1)"]
    assert plans[0]["targets"] == [{"device": vd2.STREAK_DEVICE, "command": "ExecuteRaw"}]


@pytest.mark.parametrize("frames", [1, 256, 2.5, True, "10"])
def test_invalid_values_are_rejected_without_hardware(client, monkeypatch, frames):
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("invalid value reached hardware"))
    assert client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": frames}).status_code == 400


def test_non_live_acquisition_is_not_reconfigured(client, monkeypatch):
    proxy = Proxy("busy,Acquire")
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    assert client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": 10}).status_code == 503
    assert proxy.writes == []


def test_failed_readback_does_not_enable_filter_or_retry(client, monkeypatch):
    proxy = Proxy(mismatch=True)
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    response = client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": 10})
    assert response.status_code == 503
    assert proxy.writes == ["CamParamSet(Live,RecurNumber2,10)"]


@pytest.mark.parametrize("phase", ["acquiring", "saving", "processing"])
def test_his_recording_is_not_modified(client, monkeypatch, phase):
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": phase}))
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("must not modify active HIS acquisition"))
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    assert client.post("/api/pump-probe-vd2/live/rolling-average", json={"enabled": True, "frames": 10}).status_code == 503
