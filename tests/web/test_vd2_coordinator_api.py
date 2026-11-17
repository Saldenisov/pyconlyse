import json
from threading import Lock
from types import SimpleNamespace

from flask import Blueprint, Flask, jsonify, request
import numpy as np
import pytest

from web.backend.vd2_coordinator_api import install_vd2_coordinator_routes


def test_web_live_and_optics_requests_use_coordinator_and_real_ccd_metadata():
    name, ccd_name = "vd2/experiment/controller", "vd2/camera/dcam"
    app = Flask(__name__)
    blueprint = Blueprint("vd2_test", __name__, url_prefix="/api/pump-probe-vd2")
    events = []

    class TestCoordinator:
        running = False

        def set_timeout_millis(self, timeout):
            pass

        def command_inout(self, command, *args):
            if command == "GetState":
                return json.dumps({"state": "RUNNING" if self.running else "ON",
                                   "time_range": "2 us", "error": "", "frames": 5 if self.running else 0})
            events.append((command, args))
            self.running = command == "StartLive"
            return args[0] if args else None

    coordinator = TestCoordinator()
    ccd = SimpleNamespace(set_timeout_millis=lambda timeout: None,
                          RawFrame=np.zeros((2, 4), dtype=np.uint16), FrameStamp=5, FrameTimestampUs=1_000_000)
    api = SimpleNamespace(
        pump_probe_vd2_api=blueprint, VD2_COORDINATOR_DEVICE=name, VD2_COORDINATOR_CCD=ccd_name,
        _preview_lock=Lock(), _serialized_vd2_mutation=lambda fn: fn,
        _mutation_payload=lambda fields: (request.get_json() or {}, None),
        _approval_or_response=lambda action, targets, args, route, fields: None,
        _target=lambda device, command: {"device": device, "command": command},
        _control_error=str, _to_display_pixels=lambda data, bpp: bytes(len(data) // bpp),
        DeviceProxy=lambda device: {name: coordinator, ccd_name: ccd}[device],
        tango_optics=SimpleNamespace(VD2_GRATING_BLAZE_NM={3: 500}),
    )
    for path, method in (
        ("/parameter/time_range", "POST"), ("/command/StartLive", "POST"),
        ("/preview", "GET"), ("/protocol/start", "POST"), ("/command/StopAcquisition", "POST"),
    ):
        blueprint.add_url_rule(path, endpoint=path, view_func=lambda: "Legacy handler", methods=[method])
    install_vd2_coordinator_routes(api)
    app.register_blueprint(blueprint)
    client = app.test_client()
    root = "/api/pump-probe-vd2"
    response = client.post(root + "/parameter/time_range", json={"value": "2 us"})
    assert response.json["value"] == "2 us"
    response = client.post(root + "/command/StartLive", json={})
    assert response.json["readout_backend"] == "tango"
    assert response.json["acquisition_mode"] == "Live"
    preview = client.get(root + "/preview").json
    assert preview["frame_available"] and preview["frame_stamp"] == 5
    assert preview["width"] == 4 and preview["height"] == 2
    assert client.get(root + "/preview").json["received_at"] == preview["received_at"]
    assert client.post(root + "/protocol/start", json={}).status_code == 409
    assert client.post(root + "/coordinator/prepare-measurement", json={}).json["success"]
    assert client.post(root + "/command/StopAcquisition", json={}).json["acquisition_status"] == "idle"
    assert events == [("SetTimeRange", ("2 us",)), ("StartLive", ()), ("PrepareMeasurement", ()), ("StopLive", ())]


def test_web_checks_approval_before_opening_a_coordinator_proxy():
    app = Flask(__name__)
    routes = Blueprint("vd2_denied", __name__, url_prefix="/vd2")

    def unexpected_proxy(name):
        pytest.fail(f"Unapproved request created proxy to {name}")

    routes.add_url_rule("/command/StartLive", view_func=lambda: "Legacy handler", methods=["POST"])
    install_vd2_coordinator_routes(SimpleNamespace(
        pump_probe_vd2_api=routes, VD2_COORDINATOR_DEVICE="vd2/experiment/controller",
        _serialized_vd2_mutation=lambda fn: fn,
        _mutation_payload=lambda fields: ({}, None),
        _approval_or_response=lambda action, targets, args, route, fields: (jsonify(success=False), 403),
        _target=lambda device, command: {"device": device, "command": command},
        _control_error=str, DeviceProxy=unexpected_proxy,
    ))
    app.register_blueprint(routes)
    assert app.test_client().post("/vd2/command/StartLive", json={}).status_code == 403
