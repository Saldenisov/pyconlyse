"""Offline V0 migration checks across run control, RAW lineage and HTTP recipes."""

from copy import deepcopy
from io import StringIO
from pathlib import Path
import sys

import h5py
import numpy as np
import pytest
from flask import Flask

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pump_probe_v0_api as api
from pump_probe_v0_dataset import V0Dataset, export_dat

EMULATOR_LOOP = api.PumpProbeV0Controller._run_emulator_loop


@pytest.fixture
def controlled_scan(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(api, "PIXELS", 2)
    monkeypatch.setattr(api.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(api.PumpProbeV0Controller, "_run_emulator_loop", lambda *_: None)
    monkeypatch.setattr(api, "_tango_proxy", lambda *_a, **_k: pytest.fail("Offline scan must not access devices"))
    controller = api.PumpProbeV0Controller()
    controller.configure({"delay_points_ps": [3, 3, 1], "real_zero_ps": 0, "pulses_per_point": 2})
    return controller, tmp_path


def _shots(controller, count):
    with controller._lock:
        for _ in range(count):
            controller._position_mm = controller._set_position_mm
            controller._apply_pulse_locked()


def test_partial_point_continue_preserves_parent_raw_and_row_identity(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory), "sample_name": "resume"})
    _shots(controller, 3)
    stopped = controller.set_running(False)
    parent = stopped["run"]["artifacts"]
    original_bytes = Path(parent["h5"]).read_bytes()
    original_heatmap = deepcopy(stopped["heatmap"])
    assert parent["frame_counts"] == [2, 1, 0]
    assert stopped["run"]["resume_available"] is True
    assert stopped["delays"] == [3, 3, 1]

    resumed = controller.set_running(True, {"run_action": "continue"})
    assert resumed["run"]["id"] != parent["run_id"]
    assert resumed["current_index"] == 1 and resumed["pulses_at_point"] == 1
    assert resumed["total_pulses"] == 3
    assert resumed["heatmap"][:2] == original_heatmap[:2]
    _shots(controller, 3)
    completed = controller.state()
    child = completed["run"]["artifacts"]
    assert completed["run"]["status"] == "completed"
    assert completed["run"]["resume_available"] is False
    assert child["frame_counts"] == [2, 2, 2]
    assert child["parent_run_id"] == parent["run_id"]
    assert Path(parent["h5"]).read_bytes() == original_bytes
    with h5py.File(parent["h5"], "r") as old, h5py.File(child["h5"], "r") as new:
        np.testing.assert_array_equal(old["raw_data"][0], new["raw_data"][0])
        np.testing.assert_array_equal(old["raw_data"][1, :, 0], new["raw_data"][1, :, 0])
        np.testing.assert_array_equal(new["delay_ps"], [3, 3, 1])


def test_continue_requires_same_plan_and_cancel_invalidates_checkpoint(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory)})
    _shots(controller, 1)
    stopped = controller.set_running(False)
    controller.configure({"pulses_per_point": 3})
    assert controller.state()["run"]["resume_available"] is False
    with pytest.raises(ValueError, match="matches the current scan plan"):
        controller.set_running(True, {"run_action": "continue"})
    controller.configure({"pulses_per_point": 2})
    assert controller.state()["run"]["resume_available"] is True
    cancelled = controller.set_running(False, {"run_action": "cancel"})
    assert cancelled["run"]["status"] == "aborted"
    assert cancelled["run"]["resume_available"] is False
    assert Path(stopped["run"]["artifacts"]["h5"]).exists()


def test_invalid_physical_plan_rejected_before_run_or_file_mutation(controlled_scan):
    controller, directory = controlled_scan
    controller.configure({"delay_points_ps": [0, 20000]})
    controller._heatmap = [[42, 42], [43, 43]]
    before = deepcopy(controller.state())
    with pytest.raises(ValueError, match="outside stage limits"):
        controller.set_running(True, {"save_path": str(directory)})
    assert controller.state() == before
    assert list(directory.iterdir()) == []


def test_previous_run_worker_cannot_advance_new_writer(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory)})
    old_id = controller._run_writer.run_id
    controller.set_running(False)
    controller.set_running(True, {"save_path": str(directory), "run_action": "overwrite"})
    # A stale worker must return before synchronizing the new acquisition.
    synchronize = controller._sync_locked
    controller._sync_locked = lambda: pytest.fail("Old worker advanced a new run")
    EMULATOR_LOOP(controller, old_id)
    controller._sync_locked = synchronize
    assert controller._run_writer.run_id != old_id
    assert controller._run_writer.artifacts()["frame_counts"] == [0, 0, 0]
    controller.set_running(False, {"run_action": "cancel"})


def test_rejected_start_does_not_advance_realtime_context(controlled_scan):
    controller, directory = controlled_scan
    controller.configure({"delay_points_ps": [0, 20000]})
    controller._real_time = True
    controller._sync_locked = lambda: pytest.fail("Rejected Start advanced realtime acquisition")
    with pytest.raises(ValueError, match="outside stage limits"):
        controller.set_running(True, {"save_path": str(directory)})


def test_manual_jog_rejected_during_scan_and_stage_stop_saves_checkpoint(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory)})
    _shots(controller, 1)
    target = controller._set_position_mm
    with pytest.raises(RuntimeError, match="Stop the active run"):
        controller.move_stage({"delta_mm": 1})
    assert controller._set_position_mm == target
    assert controller._run_writer.artifacts()["frame_counts"] == [1, 0, 0]
    stopped = controller.stop_stage()
    assert stopped["running"] is False
    assert stopped["run"]["resume_available"] is True
    assert stopped["run"]["artifacts"]["frame_counts"] == [1, 0, 0]


def test_unexpected_target_does_not_commit_shot_at_wrong_delay(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory)})
    controller._set_position_mm += 1
    controller._position_mm = controller._set_position_mm
    controller._apply_pulse_locked()
    state = controller.state()
    assert state["run"]["status"] == "fault"
    assert state["run"]["artifacts"]["frame_counts"] == [0, 0, 0]
    assert state["total_pulses"] == 0


def test_rejected_raw_frame_does_not_increment_committed_counts(controlled_scan):
    controller, directory = controlled_scan
    controller.set_running(True, {"save_path": str(directory)})
    controller._emulator_raw_cycle_locked = lambda _index: [[1.0]] * 6
    _shots(controller, 1)
    state = controller.state()
    assert state["run"]["status"] == "fault"
    assert state["run"]["artifacts"]["frame_counts"] == [0, 0, 0]
    assert state["total_pulses"] == 0 and state["spectrometer_frames"] == 0
    with h5py.File(state["run"]["artifacts"]["h5"], "r") as saved:
        assert np.isnan(saved["raw_data"][...]).all()


def test_tango_context_does_not_display_synthetic_emulator_od_or_spectra(controlled_scan, monkeypatch):
    controller, _directory = controlled_scan
    # Motion status has its own passive transport; this check isolates the
    # acquisition context from both motion reads and camera commands.
    monkeypatch.setattr(controller, "_read_tango_motion_state_locked", lambda state: state)
    state = controller.configure({"control_mode": "tango"})
    assert state["live_od"] == [None, None]
    assert state["heatmap"] == [[None, None]] * 3
    assert state["spectra"] == {
        "reference": [None, None], "signal": [None, None],
        "background": [None, None], "background_available": False,
    }
    assert state["run"]["acquisition_contract"] == "andor-two-track-spectra-v1"


@pytest.fixture
def data_client(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(api, "_tango_proxy", lambda *_a, **_k: pytest.fail("Treatment must not access devices"))
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    with app.test_client() as client:
        yield client, tmp_path


def _save_source(client, directory, name, delays, waves, rows):
    path = directory / name
    path.write_text(export_dat(V0Dataset(np.asarray(waves), np.asarray(delays), np.asarray(rows))), encoding="utf-8")
    loaded = client.post("/api/pump-probe-v0/data/load", json={"path": str(path)})
    assert loaded.status_code == 200
    result = loaded.get_json()
    return {"path": result["path"], "source_sha256": result["source_sha256"]}


def test_derived_average_recipe_replay_export_and_changed_source(data_client):
    client, directory = data_client
    first = _save_source(client, directory, "a.dat", [0, 0, 1], [500, 600], [[2, 2], [9, 9], [6, 6]])
    second = _save_source(client, directory, "b.dat", [1, 0], [500, 600], [[10, 10], [6, 6]])
    originals = {item["path"]: Path(item["path"]).read_bytes() for item in (first, second)}
    derived = client.post("/api/pump-probe-v0/data/derive", json={"method": "average", "sources": [first, second]})
    assert derived.status_code == 200, derived.get_json()
    source = derived.get_json()
    assert source["delays"] == [0, 0, 1]
    assert source["heatmap"] == [[4, 4], [4, 4], [8, 8]]
    assert "raw_od" not in source["capabilities"]
    recipe = {key: source[key] for key in ("path", "source_sha256", "source_spec")}
    recipe["operations"] = [{"kind": "scale", "factor": 2}]
    corrected = client.post("/api/pump-probe-v0/data/treat", json=recipe)
    assert corrected.status_code == 200, corrected.get_json()
    assert corrected.get_json()["heatmap"] == [[8, 8], [8, 8], [16, 16]]
    assert client.post("/api/pump-probe-v0/data/treat", json=recipe).get_json() == corrected.get_json()
    exported = client.post("/api/pump-probe-v0/data/treat", json={**recipe, "format": "dat"})
    np.testing.assert_array_equal(np.loadtxt(StringIO(exported.text))[1:, 1:].T, [[8, 8], [8, 8], [16, 16]])
    assert all(Path(path).read_bytes() == data for path, data in originals.items())
    Path(first["path"]).write_bytes(b"0\t0\n500\t7\n600\t8\n")
    stale = client.post("/api/pump-probe-v0/data/treat", json=recipe)
    assert stale.status_code == 400 and "Source file changed" in stale.get_json()["error"]


def test_spectral_merge_keeps_selected_column_order_and_rejects_unequal_delays(data_client):
    client, directory = data_client
    first = _save_source(client, directory, "a.dat", [1, 0], [600, 500], [[1, 2], [3, 4]])
    second = _save_source(client, directory, "b.dat", [1, 0], [700], [[5], [6]])
    request = {"method": "merge", "sources": [first, second]}
    merged = client.post("/api/pump-probe-v0/data/derive", json=request)
    assert merged.status_code == 200, merged.get_json()
    assert merged.get_json()["wavelengths"] == [600, 500, 700]
    assert merged.get_json()["heatmap"] == [[1, 2, 5], [3, 4, 6]]
    wrong = _save_source(client, directory, "wrong.dat", [0, 1], [700], [[5], [6]])
    denied = client.post("/api/pump-probe-v0/data/derive", json={**request, "sources": [first, wrong]})
    assert denied.status_code == 400


@pytest.mark.parametrize("operations", [{}, None, False])
def test_derived_endpoint_does_not_silently_drop_invalid_empty_recipes(data_client, operations):
    client, directory = data_client
    source = _save_source(client, directory, "a.dat", [0, 1], [500], [[1], [2]])
    response = client.post("/api/pump-probe-v0/data/derive", json={
        "method": "average", "sources": [source, source], "operations": operations,
    })
    assert response.status_code == 400
    assert "Recipe must be a list" in response.get_json()["error"]


def test_derivation_rejects_outside_root_even_with_correct_hash(data_client, tmp_path):
    import hashlib
    client, directory = data_client
    inside = _save_source(client, directory, "a.dat", [0, 1], [500], [[1], [2]])
    outside = tmp_path.parent / (tmp_path.name + "-outside.dat")
    content = b"0\t0\t1\n500\t1\t2\n"
    outside.write_bytes(content)
    try:
        denied = client.post("/api/pump-probe-v0/data/derive", json={"method": "average", "sources": [
            inside, {"path": str(outside), "source_sha256": hashlib.sha256(content).hexdigest()},
        ]})
        assert denied.status_code == 400
    finally:
        outside.unlink()
