"""End-to-end paired recording with a fake clock and numbered raw camera frames."""
import base64
from contextlib import contextmanager
from dataclasses import replace
import json
from threading import Event
from types import SimpleNamespace

from flask import Flask, jsonify
import h5py
import numpy as np
import pytest

from tests.web.test_pump_probe_vd2_api import vd2_api_module as api
from vd2_paired_acquisition import PairedAcquisition, PairedRequest
from vd2_paired_analysis import DetectorROI
from vd2_paired_storage import DarkReference


ROI = DetectorROI(0, 1, 0, 0, 2, 1)
SETTINGS = {"time_range": "1 us", "streak_mode": "Operate", "gate_mode": "Normal",
            "mcp_gain": "20", "acquire_exposure_time": "10 ms", "live_exposure_time": "10 ms",
            "streak_shutter": "Open", "spectrograph_shutter": "Open"}


@pytest.fixture
def rig(tmp_path):
    events = []
    source = {"id": "dark", "h5": {"path": "BRUIT.h5"}, "machine_before": {"streak_control": {"values": SETTINGS}}}
    dark = DarkReference("dark", source, np.full((2, 1), 10.), (np.full((2, 1), 10.),) * 4,
                         np.array([500, 600]), np.array([0]), "ns", "")
    control = SimpleNamespace(_machine_snapshot=lambda camera: {"streak_control": {"values": SETTINGS}},
                              equivalent=api.equivalent, _remoteex_readback=lambda *args: "0",
                              _assert_preparation_idle=lambda *args, **kwargs: None)

    @contextmanager
    def clock(_api, camera, trigger, stop, arm):
        events.append(("warm", trigger))
        arm()
        try:
            yield True
        finally:
            events.append("pulses-paused")

    run = PairedAcquisition(clock=clock, dark_reader=lambda *args: dark, project_writer=lambda *args: 'manifest')
    request = PairedRequest(str(tmp_path), "sample", "latest", "fixed", True, 3, None, "external_rising", ROI)
    return run, request, control, events


class Camera:
    def __init__(self, events, *, gap=None, no_light=False, pause_at=None):
        self.events, self.gap, self.no_light, self.pause_at = events, gap, no_light, pause_at
        self.blocked = Event()
        self.index = 0

    def set_timeout_millis(self, _):
        pass

    def command_query(self, command):
        return command

    def command_inout(self, command, arg=None):
        if command != "ReadPairedLiveFrame":
            self.events.append(command)
            return None
        index = self.index
        if index == self.pause_at:
            self.blocked.set()
            return ""
        self.index += 1
        assert arg == (-1 if index == 0 else 100 + index)
        frame = (90, 105) if index % 2 == 0 else (110, 85)
        if self.no_light:
            frame = (10, 10)
        pixels = np.array(frame, dtype="<u2")
        return json.dumps({"width": 2, "height": 1, "bytes_per_pixel": 2, "sequence": 100 + index,
                           "timestamp_ms": 1000 + 100 * (index + int(index == self.gap)),
                           "pixels_b64": base64.b64encode(pixels.tobytes()).decode()})


@pytest.mark.parametrize(("first", "pairs"), [(True, 200), (False, 3)])
def test_fixed_pairs_keep_native_raw_and_operator_phase(rig, first, pairs):
    run, request, control, events = rig
    camera = Camera(events)
    control._proxy = lambda: camera
    run.start(control, replace(request, first_map_with_electrons=first, pair_limit=pairs))
    run.wait(5)
    result = run.status()
    assert result["stop_reason"] == "pair_count_reached" and result["frames_recorded"] == 2 * pairs
    assert events == [("warm", 1), "StartPairedLive", "pulses-paused", "StopPairedLive"]
    with h5py.File(result["h5_path"]) as file:
        np.testing.assert_array_equal(file["camera_sequence"][:], np.arange(100, 100 + 2 * pairs))
        np.testing.assert_array_equal(file["beam_on"][:], [int(first), int(not first)] * pairs)
        np.testing.assert_array_equal(file["raw_data"][0, :, 0], [90, 105])
        np.testing.assert_allclose(file["paired_od"][:, 0],
                                   np.log10([100 / 80, 75 / 95]) * (1 if first else -1))
        assert file["metadata"].attrs["status"] == "completed"


def test_precision_stops_after_enough_completed_blocks(rig):
    run, request, control, events = rig
    camera = Camera(events)
    control._proxy = lambda: camera
    run.start(control, replace(request, mode="precision", target_mod=2., pair_limit=250))
    run.wait(10)
    result = run.status()
    assert result["stop_reason"] == "precision_reached"
    assert result["pairs_recorded"] == 180
    assert result["error_mod"] == pytest.approx(0., abs=1e-10)
    assert camera.index == 360


def test_invalid_dark_corrected_roi_cannot_trigger_automatic_success(rig):
    run, request, control, events = rig
    control._proxy = lambda: Camera(events, no_light=True)
    run.start(control, replace(request, mode="precision", target_mod=2., pair_limit=4))
    run.wait(5)
    result = run.status()
    assert result["stop_reason"] == "pair_limit" and result["error_mod"] is None
    with h5py.File(result["h5_path"]) as file:
        assert np.isnan(file["paired_od"][:]).all()


def test_gap_pauses_clock_and_saves_unclassified_frame(rig):
    run, request, control, events = rig
    control._proxy = lambda: Camera(events, gap=2)
    run.start(control, request)
    run.wait(5)
    result = run.status()
    assert result["status"] == "failed" and result["pairs_recorded"] == 1
    assert "confirm the first frame" in result["error"]
    assert events[-2:] == ["pulses-paused", "StopPairedLive"]
    with h5py.File(result["h5_path"]) as file:
        np.testing.assert_array_equal(file["beam_on"][:], [1, 0, -1])
        assert file["raw_data"].shape[0] == 3


def test_manual_stop_and_target_change_while_the_camera_is_waiting(rig):
    run, request, control, events = rig
    camera = Camera(events, pause_at=3)
    control._proxy = lambda: camera
    state = run.start(control, replace(request, mode="precision", target_mod=2., pair_limit=250))
    assert camera.blocked.wait(5)
    assert run.set_target(state["job_id"], 1.)["target_mod"] == 1.
    run.stop(state["job_id"])
    run.wait(5)
    result = run.status()
    assert (result["status"], result["frames_recorded"], result["pairs_recorded"]) == ("stopped", 3, 1)
    with h5py.File(result["h5_path"]) as file:
        assert file["raw_data"].shape[0] == 3
        assert json.loads(file["metadata"].attrs["summary"])["target_mod"] == 1.


def test_paired_http_authorizes_before_start_and_locks_legacy_control(monkeypatch, rig):
    run, request, _, _ = rig
    monkeypatch.setattr(api, "VD2_CAMERA_ONLY", True)
    monkeypatch.setattr(api, "_paired_acquisition", run)
    monkeypatch.setattr(api, "_approval_or_response", lambda *args: (jsonify(success=False), 428))
    monkeypatch.setattr(run, "start", lambda *args: pytest.fail("Unapproved hardware run"))
    from treatment_api import __dict__ as treatment_globals
    monkeypatch.setitem(treatment_globals, "_ensure_within_allowed_root", lambda root: root)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_vd2_api)
    client = app.test_client()
    payload = {"output_root": request.output_root, "sample_name": "sample", "reuse_bruit": "latest",
               "mode": "fixed", "first_map_with_electrons": False, "pair_limit": 4, "target_mod": None,
               "trigger_source": "external_rising", "roi": None}
    assert client.post("/api/pump-probe-vd2/paired/start", json=payload).status_code == 428
    run._update(active=True, status="acquiring")
    assert client.post("/api/pump-probe-vd2/command/StartLive", json={}).status_code == 409
    state = client.get("/api/pump-probe-vd2/protocol/state").json
    assert state["acquisition_active"] and state["paired_available"]


def test_legacy_camera_server_is_rejected_before_warmup(rig):
    run, request, control, events = rig
    camera = Camera(events)

    def missing(command):
        raise RuntimeError("API_CommandNotFound")

    camera.command_query = missing
    control._proxy = lambda: camera
    run.start(control, request)
    run.wait(5)
    assert run.status()["status"] == "failed"
    assert "Paired camera command unavailable before warm-up" in run.status()["error"]
    assert events == []


def test_real_bruit_and_paired_history_round_trip(rig, tmp_path):
    from vd2_paired_storage import load_dark_reference
    from vd2_project_manifest import MANIFEST_NAME, SCHEMA, fingerprint, inspect_project, record_paired_project_run

    run, request, control, events = rig
    bruit = tmp_path / "BRUIT.h5"
    with h5py.File(bruit, "w") as file:
        file.create_dataset("raw_data", data=np.full((8, 2, 1), 10, dtype=np.uint16))
        file.create_dataset("wavelengths", data=[500., 600.])
        file.create_dataset("timedelays", data=[0.])
        file.create_group("metadata").attrs["time_scale"] = "ns"
    manifest = tmp_path / MANIFEST_NAME
    manifest.write_text(json.dumps({
        "schema": SCHEMA, "version": 1, "project_id": "project",
        "samples": {"noise": {"name": "noise", "folder": "noise", "phases": {"BRUIT": "dark"}}},
        "artifacts": {"dark": {"id": "dark", "sample": "noise", "phase": "BRUIT",
                               "status": "completed", "completed_at": "2026-11-10T10:00:00Z",
                               "h5": {"path": bruit.name, **fingerprint(bruit)},
                               "machine_before": {"streak_control": {"values": SETTINGS}}}},
    }), encoding="utf-8")
    run._dark_reader = load_dark_reference
    run._project_writer = record_paired_project_run
    control._proxy = lambda: Camera(events)
    run.start(control, request)
    run.wait(5)
    status = run.status()
    assert status["manifest_path"] == str(manifest)
    sample = next(item for item in inspect_project(manifest)["samples"] if item["name"] == "sample")
    recorded = sample["paired_runs"][0]
    assert recorded["pairs_recorded"] == 3 and recorded["bruit_artifact_id"] == "dark"
    assert recorded["h5"]["sha256"] == fingerprint(status["h5_path"])["sha256"]
