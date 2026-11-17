"""DCAM lifecycle uses the single VD2 owner and never invokes HPD-TA."""

from types import SimpleNamespace

from flask import Blueprint, Flask, jsonify, request
import numpy as np
import pytest

from web.backend import vd2_dcam_api as dcam


@pytest.fixture
def setup(monkeypatch):
    calls = []
    camera = SimpleNamespace(
        get_trigger_mode=lambda: "ext", get_exposure=lambda: 0.02,
        set_trigger_mode=lambda mode: mode, set_exposure=lambda exposure: None,
        start_acquisition=lambda **kwargs: calls.append("start"),
        stop_acquisition=lambda: calls.append("stop"),
        close=lambda: calls.append("close"),
        read_newest_image=lambda **kwargs: (np.arange(64, dtype=np.uint16).reshape(8, 8),
                                            SimpleNamespace(framestamp=11)),
    )
    monkeypatch.setattr(dcam, "open_readout", lambda: (camera, SimpleNamespace(model="C13440-20CU")))
    monkeypatch.setattr(dcam, "require_exclusive_readout", lambda: None)
    saved = {"job": {"operation": "shutdown", "status": "completed"}}
    devices = {
        "sd2": SimpleNamespace(ids=[1, 2, 3, 4], states=[0, 1, 1, 0]),
        "vd2": SimpleNamespace(ids=[1, 2, 3, 4], states=[0, 1, 1, 0]),
        "dg": SimpleNamespace(command_inout=lambda command, query: {"TSRC?": "5", "BURM?": "0"}[query]),
    }
    routes = Blueprint("vd2", __name__, url_prefix="/api/pump-probe-vd2")

    class Steps(list):
        def power_ready(self):
            pass

    def lifecycle(operation, callback, intent=None):
        saved["job"] = dict(operation=operation, status="running", intent=intent)
        try:
            result = callback(Steps())
        except RuntimeError as exc:
            saved["job"].update(status="failed", error=str(exc))
            return jsonify(success=False, error=str(exc)), 503
        saved["job"].update(status="completed", result=result)
        return jsonify(success=True, job=saved["job"]), 202

    def switch(replacement):
        def write(pdu, steps, outputs, label):
            assert pdu is devices["sd2"] and set(outputs) == {1}
            pdu.states[0] = replacement
            calls.append(f"power {replacement}")
        return write

    api = SimpleNamespace(
        pump_probe_vd2_api=routes, ZABER_PDU_DEVICE="vd2", VD2_PDU_DEVICE="sd2", DG645_DEVICE="dg",
        STREAK_DEVICE="streak", _wait_for_device=lambda name, timeout_s: devices[name], _value=getattr,
        _lifecycle=lambda: SimpleNamespace(get=saved.get, put=saved.__setitem__), _progress=lambda *args: None,
        _enable_required_power=switch(1), _disable_pdu_outputs=switch(0),
        _mutation_payload=lambda fields: (request.get_json(silent=True) or {}, None),
        _approval_or_response=lambda *args: None, _target=lambda *args: args,
        _start_lifecycle=lifecycle, _serialized_vd2_mutation=lambda fn: fn, _control_error=str,
    )
    dcam.install_dcam_routes(api)

    @routes.post("/initialize")
    def legacy():
        return jsonify(success=True)

    @routes.post("/deinitialize")
    def legacy_shutdown():
        pytest.fail("Legacy shutdown must not operate on a DCAM-owned camera")

    app = Flask(__name__)
    app.register_blueprint(routes)
    client = app.test_client()
    return client, saved, devices, calls


BASE = "/api/pump-probe-vd2"


def test_dcam_prepare_preview_and_shutdown_release_before_power_off(setup):
    client, saved, devices, calls = setup
    assert client.post(BASE + "/dcam/prepare").status_code == 202
    assert client.get(BASE + "/dcam/state").get_json()["ready"]
    assert client.post(BASE + "/initialize").get_json()["code"] == "VD2_DCAM_ACTIVE"

    assert client.post(BASE + "/dcam/live").get_json()["success"]
    preview = client.get(BASE + "/dcam/preview").get_json()["frame"]
    assert (preview["height"], preview["width"], preview["frame_stamp"]) == (2, 2, 11)
    assert client.get(BASE + "/dcam/preview").get_json()["frame"] == preview

    assert client.post(BASE + "/deinitialize?background=1").status_code == 202
    assert calls == ["power 1", "start", "stop", "close", "power 0"]
    assert saved[dcam.OWNER_KEY] is None
    assert devices["sd2"].states == [0, 1, 1, 0]


def test_dcam_prepare_preserves_ownership_after_an_sdk_open_failure(setup, monkeypatch):
    client, saved, devices, calls = setup

    def fail():
        raise RuntimeError("DCAM offline")

    monkeypatch.setattr(dcam, "open_readout", fail)
    assert client.post(BASE + "/dcam/prepare").status_code == 503
    assert client.get(BASE + "/dcam/state").get_json()["owned"]
    assert client.post(BASE + "/initialize").status_code == 409
    assert client.post(BASE + "/dcam/unprepare").status_code == 202
    assert calls == ["power 1", "power 0"]


def test_dcam_does_not_claim_active_legacy_hardware_or_write_when_lamp_is_on(setup):
    client, saved, devices, calls = setup
    saved["job"] = {"operation": "prepare", "status": "completed"}
    assert client.post(BASE + "/dcam/unprepare").status_code == 409
    assert client.post(BASE + "/dcam/prepare").status_code == 409
    saved["job"] = {"operation": "shutdown", "status": "completed"}
    devices["vd2"].states[0] = 1
    assert client.post(BASE + "/dcam/prepare").status_code == 503
    assert calls == []
