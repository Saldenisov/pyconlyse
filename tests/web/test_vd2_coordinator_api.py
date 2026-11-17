import json
import struct
from gzip import decompress
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
        preview_pending = False
        fail_wavelength = False

        def set_timeout_millis(self, timeout):
            pass

        def command_inout(self, command, *args):
            if command == "GetState":
                return json.dumps({"state": "RUNNING" if self.running else "ON",
                                   "preview_configuration_pending": self.preview_pending,
                                   "time_range": "2 us", "error": "", "frames": 5 if self.running else 0})
            events.append((command, args))
            if command == "SetWavelength" and self.fail_wavelength:
                raise RuntimeError(SimpleNamespace(desc=(
                    "Traceback (most recent call last):\n"
                    "RuntimeError: Kymera did not confirm the new setting. Its shutter was left closed."
                )))
            if command == "SetGrating":
                self.preview_pending = True
            if command in {"StartLive", "StopLive"}:
                self.running = command == "StartLive"
            return args[0] if args else None

    coordinator = TestCoordinator()
    encoded = ("vd2-preview-v1", struct.pack("<qqHH", 1_000_000, 5, 4, 2) + np.zeros((2, 4), dtype="<u2").tobytes())
    ccd = SimpleNamespace(set_timeout_millis=lambda timeout: None, ReadPreviewFrame=lambda: encoded)
    api = SimpleNamespace(
        pump_probe_vd2_api=blueprint, VD2_COORDINATOR_DEVICE=name, VD2_COORDINATOR_CCD=ccd_name,
        _preview_lock=Lock(), _serialized_vd2_mutation=lambda fn: fn,
        _preparation_lock=Lock(),
        camera_serialization_timeout=lambda error: False,
        _protocol_hardware_phase=lambda: "idle",
        _mutation_payload=lambda fields: (request.get_json() or {}, None),
        _approval_or_response=lambda action, targets, args, route, fields: None,
        _target=lambda device, command: {"device": device, "command": command},
        _control_error=str,
        DeviceProxy=lambda device: {name: coordinator, ccd_name: ccd}[device],
        tango_optics=SimpleNamespace(VD2_GRATING_BLAZE_NM={3: 500}),
        _alignment_readout=SimpleNamespace(unavailable=lambda: None),
    )
    for path, method in (
        ("/state", "GET"), ("/parameter/time_range", "POST"), ("/command/StartLive", "POST"),
        ("/preview", "GET"), ("/protocol/start", "POST"), ("/command/StopAcquisition", "POST"),
        ("/parameter/grating_index", "POST"), ("/parameter/wavelength_nm", "POST"),
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
    compressed = client.get(root + "/preview", headers={"Accept-Encoding": "gzip"})
    assert compressed.headers["Content-Encoding"] == "gzip"
    assert json.loads(decompress(compressed.data)) == preview
    response = client.post(root + "/parameter/grating_index", json={"value": 2})
    assert response.json["value"] == 2 and response.json["acquisition_mode"] == "Live"
    pending = client.get(root + "/preview").json
    assert not pending["frame_available"] and pending["stream_state"] == "waiting_for_frame"
    coordinator.fail_wavelength = True
    response = client.post(root + "/parameter/wavelength_nm", json={"value": 600})
    assert response.status_code == 409
    assert response.json["error"] == "Kymera did not confirm the new setting. Its shutter was left closed."
    with api._preparation_lock:
        assert client.get(root + "/state").json == {
            "success": True, "readout_backend": "tango", "state_deferred": True,
        }
        assert client.get(root + "/preview").json["stream_state"] == "waiting_for_frame"
    assert client.post(root + "/protocol/start", json={}).get_data(as_text=True) == "Legacy handler"
    assert client.post(root + "/coordinator/prepare-measurement", json={}).json["success"]
    assert client.post(root + "/command/StopAcquisition", json={}).json["acquisition_status"] == "idle"
    assert events == [("SetTimeRange", ("2 us",)), ("StartLive", ()), ("SetGrating", (2,)),
                      ("SetWavelength", (600.,)), ("PrepareMeasurement", ()), ("StopLive", ())]


def test_web_checks_approval_before_opening_a_coordinator_proxy():
    app = Flask(__name__)
    routes = Blueprint("vd2_denied", __name__, url_prefix="/vd2")

    def unexpected_proxy(name):
        pytest.fail(f"Unapproved request created proxy to {name}")

    routes.add_url_rule("/command/StartLive", view_func=lambda: "Legacy handler", methods=["POST"])
    install_vd2_coordinator_routes(SimpleNamespace(
        pump_probe_vd2_api=routes, VD2_COORDINATOR_DEVICE="vd2/experiment/controller",
        _serialized_vd2_mutation=lambda fn: fn, _protocol_hardware_phase=lambda: "idle",
        _mutation_payload=lambda fields: ({}, None),
        _approval_or_response=lambda action, targets, args, route, fields: (jsonify(success=False), 403),
        _target=lambda device, command: {"device": device, "command": command},
        _control_error=str, DeviceProxy=unexpected_proxy,
    ))
    app.register_blueprint(routes)
    assert app.test_client().post("/vd2/command/StartLive", json={}).status_code == 403


def test_direct_lifecycle_uses_shared_power_sequence_and_tango_optics():
    app = Flask(__name__)
    routes = Blueprint("vd2_lifecycle", __name__, url_prefix="/vd2")
    name = "vd2/experiment/controller"
    events = []
    authorization_required = False

    class Coordinator:
        prepared = False

        def command_inout(self, command, *args):
            if command == "GetState":
                return json.dumps({"state": "ON", "prepared": self.prepared, "time_range": "1 us",
                                   "error": "", "frames": 0, "trigger_rate_hz": 5})
            events.append((command, *args))
            self.prepared = command != "Unprepare"

        def set_timeout_millis(self, timeout):
            pass

    coordinator = Coordinator()

    def initialize(steps, *, prepare_optics):
        events.append(("power verified",))
        return {"steps": steps, "device": prepare_optics()}

    def shutdown(steps, *, shutdown_optics):
        shutdown_optics()
        events.append(("camera power off",))
        return {"steps": steps}

    def start_lifecycle(operation, action, intent):
        events.append((operation, intent))
        return jsonify(success=True, result=action([])), 202

    for path in ("/initialize", "/deinitialize"):
        routes.add_url_rule(path, endpoint=path, view_func=lambda: pytest.fail("Legacy lifecycle called"), methods=["POST"])
    install_vd2_coordinator_routes(SimpleNamespace(
        pump_probe_vd2_api=routes, VD2_COORDINATOR_DEVICE=name,
        _serialized_vd2_mutation=lambda fn: fn, _mutation_payload=lambda fields: (request.json or {}, None),
        authorization_required=lambda: authorization_required,
        _exact_plan_required=lambda: (jsonify(success=False), 403),
        DeviceProxy=lambda device: {name: coordinator}[device],
        _initialize_equipment=initialize, _shutdown_equipment=shutdown,
        _protocol_hardware_phase=lambda: "idle", _start_lifecycle=start_lifecycle,
        tango_optics=SimpleNamespace(VD2_GRATING_BLAZE_NM={3: 500}),
        _control_error=str,
    ))
    app.register_blueprint(routes)
    client = app.test_client()
    result = client.post("/vd2/initialize?background=1", json={"restore_mode": "alignment", "restore_id": None})
    assert result.status_code == 202
    assert result.json["result"]["restored"] == {"ui": {"tab": "alignment"}}
    assert result.json["result"]["device"]["coordinator"]["prepared"]
    assert client.post("/vd2/deinitialize?background=1", json={}).status_code == 202
    assert events == [("prepare", {"restore_mode": "alignment"}),
                      ("power verified",), ("Prepare",), ("SetTimeRange", "1 us"),
                      ("shutdown", None), ("Unprepare",), ("camera power off",)]
    events.clear()
    assert client.post("/vd2/initialize?background=1", json={"restore_mode": "point"}).status_code == 400
    authorization_required = True
    assert client.post("/vd2/deinitialize?background=1", json={}).status_code == 403
    assert events == []
