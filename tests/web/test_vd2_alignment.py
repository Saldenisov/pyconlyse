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


@pytest.fixture(autouse=True)
def empty_preview_cache(monkeypatch):
    monkeypatch.setattr(vd2, "_preview_cache", None)
    monkeypatch.setattr(vd2, "_preview_cache_until", 0.0)


def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(vd2.pump_probe_vd2_api)
    return app.test_client()


@pytest.mark.parametrize("url", ["/alignment/start", "/alignment/calibration", "/alignment/flash-lamp", "/alignment/open-shutters"])
def test_alignment_denial_precedes_hardware(monkeypatch, url):
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("hardware accessed before authorization"))
    monkeypatch.setattr(vd2, "DeviceProxy", lambda *_: pytest.fail("hardware accessed before authorization"))
    calls = []
    def deny(**kwargs):
        calls.append(kwargs)
        return jsonify({"success": False, "code": "hardware_approval_required"}), 428
    monkeypatch.setattr(vd2, "require_http_hardware", deny)
    response = client().post("/api/pump-probe-vd2" + url, json={})
    assert response.status_code == 428
    assert calls[0]["route_id"].startswith("vd2.alignment.")
    if url.endswith("start"):
        assert calls[0]["args"]["streak_shutter"] == "Open"
        assert calls[0]["args"]["spectrograph_shutter"] == "Open"
        assert calls[0]["args"]["time_range"] == "1 us"
    elif url.endswith("flash-lamp"):
        assert calls[0]["args"] == {"target_mm": 0.0}
        assert calls[0]["targets"] == [{"device": vd2.ZABER_STAGE_DEVICE, "command": "MoveAbsoluteMm"}]
    elif url.endswith("open-shutters"):
        assert calls[0]["args"] == {"streak_shutter": "Open", "spectrograph_shutter": "Open"}


def stage(position=0.0, state="ON", **kwargs):
    return {"state": state, "position_mm": position, "minimum_mm": 0.0, "maximum_mm": 50.0, **kwargs}


@pytest.mark.parametrize("position,state_name,shutter,ready", [
    (0.01, "ON", "Open", True), (50.0, "ON", "Open", False),
    (0.0, "MOVING", "Open", False), (0.0, "ON", "Closed", False),
    (float("nan"), "ON", "Open", False),
])
def test_optics_ready_requires_finite_stopped_mirror_and_both_actual_open_readbacks(monkeypatch, position, state_name, shutter, ready):
    queries = []
    monkeypatch.setattr(vd2, "_zaber_stage_state", lambda: stage(position, state_name))
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    def readback(_, query):
        queries.append(query)
        return shutter
    monkeypatch.setattr(vd2, "_remoteex_readback", readback)
    response = client().get("/api/pump-probe-vd2/alignment/optics")
    assert response.status_code == 200
    assert response.json["ready"] is ready
    assert queries == ["DevParamGet(TD,Shutter)", "DevParamGet(Spec,Shutter)"]
    assert "NaN" not in response.get_data(as_text=True)


def test_optics_preserves_individual_read_errors(monkeypatch):
    monkeypatch.setattr(vd2, "_zaber_stage_state", lambda: stage())
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    def readback(_, query):
        if "TD" in query:
            raise RuntimeError("camera disconnected")
        return "Open"
    monkeypatch.setattr(vd2, "_remoteex_readback", readback)
    response = client().get("/api/pump-probe-vd2/alignment/optics")
    assert response.json["ready"] is False
    assert response.json["shutters"]["streak_shutter"] == {"value": "UNKNOWN", "error": "camera disconnected"}
    assert response.json["shutters"]["spectrograph_shutter"]["value"] == "Open"


@pytest.mark.parametrize("initial,expected,code", [(stage(50.0), True, 202), (stage(0.01), False, 200)])
def test_flash_lamp_only_moves_source_mirror_and_waits_for_real_readback(monkeypatch, initial, expected, code):
    calls = []
    readings = iter([initial, stage(None, "MOVING")])
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: None)
    monkeypatch.setattr(vd2, "_zaber_stage_state", lambda: next(readings))
    mirror = SimpleNamespace(set_timeout_millis=lambda _: None,
                             command_inout=lambda *args: calls.append(args))
    def device(name):
        assert name == vd2.ZABER_STAGE_DEVICE
        return mirror
    monkeypatch.setattr(vd2, "DeviceProxy", device)
    response = client().post("/api/pump-probe-vd2/alignment/flash-lamp", json={})
    assert response.status_code == code
    assert response.json["command_sent"] is expected
    assert calls == ([("MoveAbsoluteMm", 0.0)] if expected else [])
    assert response.json["zaber_mirror"]["at_flash_lamp"] is (not expected)


@pytest.mark.parametrize("initial", [stage(50, error="USB unavailable"), stage(50, "MOVING"),
                                      stage(50, minimum_mm=1.0), stage(float("nan"))])
def test_flash_lamp_rejects_faults_motion_invalid_position_or_limits(monkeypatch, initial):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: None)
    monkeypatch.setattr(vd2, "_zaber_stage_state", lambda: initial)
    monkeypatch.setattr(vd2, "DeviceProxy", lambda *_: pytest.fail("must not move"))
    assert client().post("/api/pump-probe-vd2/alignment/flash-lamp", json={}).status_code == 503


@pytest.mark.parametrize("url", ["flash-lamp", "open-shutters"])
def test_camera_setup_actions_do_not_race_active_measurement(monkeypatch, url):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: (_ for _ in ()).throw(RuntimeError("Measurement busy")))
    monkeypatch.setattr(vd2, "_zaber_stage_state", lambda: pytest.fail("must not touch mirror"))
    response = client().post("/api/pump-probe-vd2/alignment/" + url, json={})
    assert response.status_code == 503
    assert response.json["error"] == "Measurement busy"


@pytest.mark.parametrize("first_readback,expected_writes,code", [("Open", 2, 200), ("Closed", 1, 503)])
def test_open_shutters_verifies_each_readback_without_starting_acquisition(monkeypatch, first_readback, expected_writes, code):
    writes = []
    proxy = SimpleNamespace(write_attribute=lambda *args: writes.append(args))
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: None)
    monkeypatch.setattr(vd2, "_remoteex_readback", lambda _, query: first_readback if "TD" in query else "Open")
    response = client().post("/api/pump-probe-vd2/alignment/open-shutters", json={})
    assert response.status_code == code
    assert writes == [("streak_shutter", "Open"), ("spectrograph_shutter", "Open")][:expected_writes]


def test_align_verifies_settings_before_live_and_never_writes_magnets(monkeypatch):
    calls = []
    class Proxy:
        def write_attribute(self, name, value):
            calls.append((name, value))
        def read_attribute(self, name):
            return SimpleNamespace(value="Open")
        def command_inout(self, command, value=None):
            calls.append((command, value))
    proxy = Proxy()
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: calls.append("idle verified"))
    monkeypatch.setattr(vd2, "_remoteex_readback", lambda _, query: "Operate" if "Mode" in query else "1 us")
    monkeypatch.setattr(vd2, "_apply_vd2_timing", lambda *_: calls.append("timing applied"))
    monkeypatch.setattr(vd2, "_verify_vd2_timing_ready", lambda _: calls.append("timing verified"))
    monkeypatch.setattr(vd2, "_snapshot", lambda _: {})
    assert client().post("/api/pump-probe-vd2/alignment/start", json={}).status_code == 200
    assert calls == ["idle verified", ("streak_mode", "Operate"), ("time_range", "1 us"),
                     "timing applied", ("streak_shutter", "Open"),
                     ("spectrograph_shutter", "Open"), "timing verified", ("StartLive", None)]


@pytest.mark.parametrize("status,code", [("idle", 200), ("busy,Live", 200), ("busy,Acquire", 503)])
def test_calibration_supports_live_without_stopping_acquisition(monkeypatch, status, code):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(vd2, "_remoteex_readback", lambda _, query: status if query == "AcqStatus()" else pytest.fail("Unexpected hardware query"))
    captured = []
    monkeypatch.setattr(vd2, "_capture_alignment_axes", lambda _: captured.append(True) or {"source": "current_hpdta_img"})
    assert client().post("/api/pump-probe-vd2/alignment/calibration", json={}).status_code == code
    assert captured == ([True] if code == 200 else [])


@pytest.mark.parametrize("phase", ["acquiring", "saving", "processing"])
def test_automatic_calibration_never_interferes_with_his(monkeypatch, phase):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": phase}))
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("Active HIS must not be touched"))
    assert client().post("/api/pump-probe-vd2/alignment/calibration", json={}).status_code == 503


@pytest.mark.parametrize("stage", ["status", "raw_status", "save"])
def test_empty_image_calibration_waits_without_stale_axes_or_command_replay(monkeypatch, tmp_path, stage):
    calls = []
    monkeypatch.setattr(vd2.time, "monotonic", lambda: 20.0)
    monkeypatch.setattr(vd2, "_preview_cache", ({"success": True, "frame_available": True, "pixels_b64": "stale"}, 200))
    monkeypatch.setattr(vd2, "_preview_cache_until", 21.0)
    path = tmp_path / "owned-calibration.img"
    command = f"ImgSave(Current,IMG,{path},1)" if stage == "save" else "ImgStatusGet(Current,All)"
    source = "ImgSave" if stage == "save" else "ImgStatusGet"
    detail = (f"Invalid {command} readback: 7,{source},No valid image" if stage == "raw_status"
              else f"RemoteEx command failed for '{command}': 7,{source},No valid image")
    def fail():
        raise RuntimeError(SimpleNamespace(desc=detail))
    def signature(_):
        if stage != "save":
            fail()
        return {"time_range": "1 us", "wavelength_nm": "550", "grating": "150 g/mm"}
    def save(*args):
        calls.append(args)
        fail()
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(vd2, "_proxy", lambda: SimpleNamespace(command_inout=save))
    monkeypatch.setattr(vd2, "_assert_alignment_live_or_idle", lambda _: None)
    monkeypatch.setattr(vd2, "_alignment_image_path", path)
    monkeypatch.setattr(vd2, "_alignment_signature", signature)
    monkeypatch.setattr(vd2, "_alignment_axes", {"stale": True})
    monkeypatch.setattr(vd2, "read_alignment_axes", lambda _: pytest.fail("No image to calibrate"))
    response = client().post("/api/pump-probe-vd2/alignment/calibration", json={})
    assert response.status_code == 200
    assert response.json == {"success": True, "frame_available": False, "calibration": None,
                             "stream_state": "no_valid_image", "source_status": f"7,{source},No valid image"}
    assert vd2._alignment_axes is None
    assert calls == ([("SaveCurrentImage", str(path))] if stage == "save" else [])
    assert not path.exists()
    preview = client().get("/api/pump-probe-vd2/preview").json
    assert preview == {key: value for key, value in response.json.items() if key != "calibration"}


@pytest.mark.parametrize("detail", [
    "RemoteEx command failed for 'ImgStatusGet(Current,All)': 9,ImgStatusGet,No valid image",
    "API_DeviceTimedOut: ImgStatusGet(Current,All)",
])
def test_real_calibration_failures_remain_errors(monkeypatch, detail):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_assert_alignment_live_or_idle", lambda _: None)
    monkeypatch.setattr(vd2, "_capture_alignment_axes", lambda _: (_ for _ in ()).throw(RuntimeError(detail)))
    response = client().post("/api/pump-probe-vd2/alignment/calibration", json={})
    assert response.status_code == 503
    assert response.json == {"success": False, "error": detail}


def test_changed_image_settings_remove_cached_axes_without_saving_on_get(monkeypatch):
    signature = {"time_range": "1 us", "wavelength_nm": "600", "grating": "150 g/mm"}
    proxy = SimpleNamespace(state=lambda: "ON", read_attribute=lambda _: SimpleNamespace(value=True))
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(vd2, "_read_display_frame", lambda _: {"width": 2, "height": 3})
    monkeypatch.setattr(vd2, "_alignment_frame_metadata", lambda _: (signature.copy(), {"lut": "fixed"}))
    monkeypatch.setattr(vd2, "_alignment_axes", {"width": 2, "height": 3, "settings": signature.copy()})
    first = client().get("/api/pump-probe-vd2/preview").json
    assert first["calibration"]["settings"]["wavelength_nm"] == "600"
    signature["wavelength_nm"] = "700"
    monkeypatch.setattr(vd2, "_preview_cache_until", 0.0)
    second = client().get("/api/pump-probe-vd2/preview").json
    assert "calibration" not in second
    assert first["calibration_key"] != second["calibration_key"]


def test_capture_only_saves_current_image_and_checks_acquired_settings(monkeypatch, tmp_path):
    signature = {"time_range": "1 us", "wavelength_nm": "600", "grating": "150 g/mm"}
    calls = []
    proxy = SimpleNamespace(command_inout=lambda *args: calls.append(args))
    path = tmp_path / "owned-alignment.img"
    monkeypatch.setattr(vd2, "_alignment_image_path", path)
    monkeypatch.setattr(vd2, "_alignment_axes", None)
    monkeypatch.setattr(vd2, "_alignment_signature", lambda _: signature.copy())
    monkeypatch.setattr(vd2, "read_alignment_axes", lambda _: {"width": 2, "height": 3, "acquisition_settings": signature.copy()})
    axes = vd2._capture_alignment_axes(proxy)
    assert calls == [("SaveCurrentImage", str(path))]
    assert axes["settings"] == signature
    assert len(axes["calibration_key"]) == 64


def test_align_does_not_touch_hardware_when_another_measurement_is_busy(monkeypatch):
    monkeypatch.setattr(vd2, "_approval_or_response", lambda *args: None)
    monkeypatch.setattr(vd2, "_proxy", lambda: object())
    monkeypatch.setattr(vd2, "_assert_preparation_idle", lambda _: (_ for _ in ()).throw(RuntimeError("Measurement busy")))
    response = client().post("/api/pump-probe-vd2/alignment/start", json={})
    assert response.status_code == 503
    assert response.json["error"] == "Measurement busy"


@pytest.mark.parametrize("stage", ["saving", "processing"])
def test_preview_does_not_race_native_file_writer(monkeypatch, stage):
    proxy = SimpleNamespace(state=lambda: "ON", read_attribute=lambda _: SimpleNamespace(value=True))
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": stage}))
    monkeypatch.setattr(vd2, "_read_display_frame", lambda _: pytest.fail("preview raced save"))
    response = client().get("/api/pump-probe-vd2/preview")
    assert response.json == {"success": True, "frame_available": False, "stream_state": stage}


@pytest.mark.parametrize("stage", ["acquiring", "completed"])
def test_sequence_and_idle_last_frame_are_readable(monkeypatch, stage):
    proxy = SimpleNamespace(state=lambda: "ON", read_attribute=lambda name: SimpleNamespace(value=True if name == "application_running" else "idle"))
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": stage}))
    monkeypatch.setattr(vd2, "_alignment_axes", None)
    monkeypatch.setattr(vd2, "_read_display_frame", lambda _: {"width": 2, "height": 3})
    response = client().get("/api/pump-probe-vd2/preview")
    assert response.json["frame_available"] is True
    assert response.json["stream_state"] == ("acquiring" if stage == "acquiring" else "last_frame")


def preview_reader(monkeypatch, read):
    proxy = SimpleNamespace(state=lambda: "ON", read_attribute=lambda name: SimpleNamespace(value=True if name == "application_running" else "busy"))
    monkeypatch.setattr(vd2, "_proxy", lambda: proxy)
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "idle"}))
    monkeypatch.setattr(vd2, "_alignment_axes", None)
    monkeypatch.setattr(vd2, "_alignment_frame_metadata", lambda _: ({"time_range": "1 us"}, {"lut": "fixed"}))
    monkeypatch.setattr(vd2, "_read_display_frame", read)


def test_shared_preview_reuses_timestamp_and_refreshes_after_period(monkeypatch):
    clock = [20.0]
    reads = []
    monkeypatch.setattr(vd2.time, "monotonic", lambda: clock[0])
    preview_reader(monkeypatch, lambda _: reads.append(True) or {"width": 2, "height": 3})
    browser = client()
    first = browser.get("/api/pump-probe-vd2/preview").json
    second = browser.get("/api/pump-probe-vd2/preview").json
    assert second == first
    assert len(reads) == 1
    assert first["intensity_key"]
    clock[0] += 0.2
    assert browser.get("/api/pump-probe-vd2/preview").json["frame_available"] is True
    assert len(reads) == 2


def test_image_removed_between_pixels_and_metadata_is_not_published_as_current(monkeypatch):
    preview_reader(monkeypatch, lambda _: {"width": 2, "height": 3})
    detail = "RemoteEx command failed for 'ImgStatusGet(Current,All)': 7,ImgStatusGet,No valid image"
    monkeypatch.setattr(vd2, "_alignment_frame_metadata", lambda _: (_ for _ in ()).throw(RuntimeError(detail)))
    response = client().get("/api/pump-probe-vd2/preview")
    assert response.status_code == 200
    assert response.json == {"success": True, "frame_available": False,
                             "stream_state": "no_valid_image", "source_status": "7,ImgStatusGet,No valid image"}
    monkeypatch.setattr(vd2, "_preview_cache_until", 0.0)
    monkeypatch.setattr(vd2, "_alignment_frame_metadata", lambda _: ({"time_range": "1 us"}, {"lut": "fixed"}))
    assert client().get("/api/pump-probe-vd2/preview").json["frame_available"]


def test_parallel_preview_does_not_queue_a_second_native_transfer(monkeypatch):
    from threading import Event, Thread
    started, release = Event(), Event()
    reads, result = [], []
    def read(_):
        reads.append(True)
        started.set()
        assert release.wait(2)
        return {"width": 2, "height": 3}
    preview_reader(monkeypatch, read)
    worker = Thread(target=lambda: result.append(client().get("/api/pump-probe-vd2/preview").json))
    worker.start()
    try:
        assert started.wait(2)
        response = client().get("/api/pump-probe-vd2/preview").json
        assert response == {"success": True, "frame_available": False, "stream_state": "waiting_for_frame"}
        assert len(reads) == 1
    finally:
        release.set()
        worker.join(2)
    assert result[0]["frame_available"] is True


def test_preview_failure_cannot_serve_previous_success_as_fresh(monkeypatch):
    preview_reader(monkeypatch, lambda _: {"width": 2, "height": 3})
    browser = client()
    assert browser.get("/api/pump-probe-vd2/preview").json["frame_available"]
    monkeypatch.setattr(vd2, "_preview_cache_until", 0.0)
    monkeypatch.setattr(vd2, "_read_display_frame", lambda _: (_ for _ in ()).throw(RuntimeError("Camera link lost")))
    for _ in range(2):
        response = browser.get("/api/pump-probe-vd2/preview")
        assert response.status_code == 503
        assert response.json == {"success": False, "error": "Camera link lost"}


def test_no_current_display_image_is_waiting_without_replay_and_recovers_on_next_frame(monkeypatch):
    clock = [20.0]
    reads = []
    detail = "RemoteExCommandError: RemoteEx command failed for 'ImgDataGet(Current,Display)': 7,ImgDataGet,No valid image\n"
    failure = RuntimeError(SimpleNamespace(desc=detail))
    def read(_):
        reads.append(True)
        if len(reads) == 2:
            raise failure
        return {"width": 2, "height": 3}
    monkeypatch.setattr(vd2.time, "monotonic", lambda: clock[0])
    preview_reader(monkeypatch, read)
    browser = client()
    assert browser.get("/api/pump-probe-vd2/preview").json["frame_available"]
    clock[0] += 0.2
    for _ in range(2):
        response = browser.get("/api/pump-probe-vd2/preview")
        assert response.status_code == 200
        assert response.json == {"success": True, "frame_available": False,
                                 "stream_state": "no_valid_image", "source_status": "7,ImgDataGet,No valid image"}
    assert len(reads) == 2
    clock[0] += 0.2
    assert browser.get("/api/pump-probe-vd2/preview").json["frame_available"]
    assert len(reads) == 3


@pytest.mark.parametrize("detail", [
    "RemoteEx command failed for 'ImgDataGet(Current,Display)': 7,ImgDataGet,Camera not connected",
    "RemoteEx command failed for 'ImgDataGet(Current,Display)': 9,ImgDataGet,No valid image",
    "RemoteEx command failed for 'ImgDataGet(Current,Data)': 7,ImgDataGet,No valid image",
    "API_DeviceTimedOut: GetCurrentDisplayFrame",
])
def test_other_image_and_transport_failures_remain_errors(monkeypatch, detail):
    preview_reader(monkeypatch, lambda _: (_ for _ in ()).throw(RuntimeError(detail)))
    response = client().get("/api/pump-probe-vd2/preview")
    assert response.status_code == 503
    assert response.json == {"success": False, "error": detail}


def test_save_phase_overrides_an_otherwise_fresh_cached_preview(monkeypatch):
    preview_reader(monkeypatch, lambda _: {"width": 2, "height": 3})
    browser = client()
    assert browser.get("/api/pump-probe-vd2/preview").json["frame_available"]
    monkeypatch.setattr(vd2, "_measurement_protocol", SimpleNamespace(status=lambda: {"status": "saving"}))
    response = browser.get("/api/pump-probe-vd2/preview")
    assert response.json == {"success": True, "frame_available": False, "stream_state": "saving"}


@pytest.mark.parametrize("failure", [False, True])
def test_parallel_viewer_shares_pending_frame_or_its_failure_without_another_native_read(monkeypatch, failure):
    from threading import Event, Lock, Thread
    started, waiting, release = Event(), Event(), Event()
    native_lock = Lock()
    class ObservedLock:
        def acquire(self, **kwargs):
            if "timeout" in kwargs:
                waiting.set()
            return native_lock.acquire(**kwargs)
        def release(self):
            native_lock.release()
    monkeypatch.setattr(vd2, "_preview_lock", ObservedLock())
    monkeypatch.setattr(vd2, "_preview_cache", ({"success": True, "width": 1}, 200))
    reads, responses = [], []
    def read(_):
        reads.append(True)
        started.set()
        assert release.wait(2)
        if failure:
            raise RuntimeError("Camera read failed")
        return {"width": 2, "height": 3}
    preview_reader(monkeypatch, read)
    def request():
        response = client().get("/api/pump-probe-vd2/preview")
        responses.append((response.status_code, response.json))
    owner, viewer = Thread(target=request), Thread(target=request)
    owner.start()
    try:
        assert started.wait(2)
        viewer.start()
        assert waiting.wait(2)
        release.set()
    finally:
        release.set()
        owner.join(2)
        if viewer.ident is not None:
            viewer.join(2)
    assert len(reads) == 1
    assert len(responses) == 2
    assert responses[0] == responses[1]
    if failure:
        assert responses[0] == (503, {"success": False, "error": "Camera read failed"})
    else:
        assert responses[0][1]["width"] == 2
        assert "received_at" in responses[0][1]


def test_snapshot_batches_cached_attributes_and_preserves_individual_faults(monkeypatch):
    monkeypatch.setattr(vd2, "READ_ATTRIBUTES", {"connected": "connected", "application_running": "application_running", "gain": "gain"})
    calls = []
    def read_many(names):
        calls.append(names)
        return [SimpleNamespace(value=True, has_failed=lambda: False),
                SimpleNamespace(value=True, has_failed=lambda: False),
                SimpleNamespace(has_failed=lambda: True, get_err_stack=lambda: ["Gain read unavailable"])]
    proxy = SimpleNamespace(read_attributes=read_many, state=lambda: "ON",
                            read_attribute=lambda _: pytest.fail("Unnecessary individual Tango read"))
    snapshot = vd2._snapshot(proxy)
    assert calls == [["connected", "application_running", "gain"]]
    assert snapshot["connected"] and snapshot["application_running"]
    assert snapshot["values"]["gain"] is None
    assert "Gain read unavailable" in snapshot["attribute_errors"]["gain"]


def test_snapshot_bulk_failure_falls_back_to_individual_readback(monkeypatch):
    monkeypatch.setattr(vd2, "READ_ATTRIBUTES", {"connected": "connected"})
    def fail(_):
        raise RuntimeError("Bulk read unavailable")
    proxy = SimpleNamespace(read_attributes=fail, read_attribute=lambda _: SimpleNamespace(value=True), state=lambda: "ON")
    assert vd2._snapshot(proxy)["connected"] is True
