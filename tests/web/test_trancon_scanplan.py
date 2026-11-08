"""Offline immutable intent and copy-on-continue storage contracts."""

import hashlib
import json
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import h5py
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))

import pump_probe_v0_storage as storage
from pump_probe_v0_scanplan import build_scan_plan


def settings(**changes):
    return {"point_count": 3, "scan_start_ps": 0., "delay_step_ps": 1.,
            "delay_points_ps": [0., 2., 0.], "pulses_per_point": 3,
            "real_zero_ps": 0., "calibration_version": "fixture-calibration-v1", **changes}


def make_plan(**changes):
    return build_scan_plan(settings(**changes), .5, -2., 2.)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frames(point, shot):
    value = np.array([[0., 0.], [10., 10.], [10. + point + shot, 0.],
                      [0., 0.], [10., 10.], [5. + shot, 0.]], dtype=np.float32)
    # Both nonfinite signs and NaN must survive replay rather than be ignored.
    if point == 1:
        value[5, 0] = 0.
    if point == 2:
        value[2, 0] = 0.
    return value


def new_writer(plan):
    return storage.V0EmulatorRunWriter([500., 600.], plan.delays, plan.positions,
                                       plan.shots_per_point, {"scan_plan": plan.to_dict()}, plan=plan)


def record(writer, point, shot):
    return writer.record_cycle(point, frames(point, shot), writer.positions[point], writer.positions[point])


def stopped_source():
    plan = make_plan()
    writer = new_writer(plan)
    record(writer, 0, 0)
    return plan, writer.finalize("stopped")


def test_plan_snapshot_is_immutable_and_preserves_order_repeats():
    source = settings()
    plan = build_scan_plan(source, .5, -2., 2.)
    snapshot = plan.to_dict()
    fingerprint = plan.fingerprint
    source["delay_points_ps"][0] = 99
    snapshot["delays_ps"][0] = 99
    assert plan.delays == (0., 2., 0.)
    assert plan.positions == (-0., -1., -0.)
    assert plan.fingerprint == fingerprint
    assert json.loads(json.dumps(plan.to_dict())) == plan.to_dict()
    with pytest.raises(FrozenInstanceError):
        plan.shots_per_point = 10
    assert replace(plan, calibration_version="fixture-calibration-v2").fingerprint != fingerprint


def test_generated_descending_and_zero_step_are_not_sorted_or_deduplicated():
    descending = make_plan(delay_points_ps=None, scan_start_ps=2., delay_step_ps=-1.)
    repeated = make_plan(delay_points_ps=[], delay_step_ps=0.)
    assert descending.delays == (2., 1., 0.)
    assert repeated.delays == (0., 0., 0.)
    assert descending.fingerprint != repeated.fingerprint


@pytest.mark.parametrize("change", [
    {"delay_points_ps": [0., 5.]},
    {"delay_points_ps": [0., float("nan")]},
    {"delay_points_ps": [0., float("inf")]},
    {"real_zero_ps": float("inf")},
    {"pulses_per_point": 1.5},
    {"delay_points_ps": [0., True]},
    {"calibration_version": ""},
])
def test_invalid_or_out_of_range_targets_are_rejected_without_clipping(change):
    before = settings(**change)
    with pytest.raises(ValueError):
        build_scan_plan(before, .5, -2., 2.)
    assert before == settings(**change)


def test_target_endpoints_are_inclusive_and_overflow_is_rejected():
    plan = make_plan(delay_points_ps=[4., -4.])
    assert plan.positions == (-2., 2.)
    with pytest.raises(ValueError, match="finite"):
        build_scan_plan(settings(delay_points_ps=[0., 1e308], real_zero_ps=1e308), 1., -2., 2.)


def test_resume_replays_partial_shots_with_nonfinite_od_and_parent_lineage():
    plan, first = stopped_source()
    first_sha = digest(first["h5_path"])
    child = storage.V0EmulatorRunWriter.resume_from(first["h5_path"], {}, expected_plan=plan,
                                                   expected_wavelengths=[500., 600.])
    assert child.run_id != first["run_id"]
    assert child.artifacts()["parent_run_id"] == first["run_id"]
    assert (child.artifacts()["next_point_index"], child.artifacts()["next_shot_index"]) == (0, 1)
    record(child, 0, 1)
    record(child, 0, 2)
    record(child, 1, 0)
    second = child.finalize("stopped")
    second_sha = digest(second["h5_path"])
    final = storage.V0EmulatorRunWriter.resume_from(second["h5_path"], {}, expected_plan=plan)
    assert (final.artifacts()["next_point_index"], final.artifacts()["next_shot_index"]) == (1, 1)
    for point, shots in ((1, range(1, 3)), (2, range(3))):
        for shot in shots:
            record(final, point, shot)
    result = final.finalize("completed")
    control = new_writer(plan)
    for point in range(3):
        for shot in range(3):
            record(control, point, shot)
    expected = control.finalize("completed")
    with h5py.File(result["h5_path"], "r") as actual, h5py.File(expected["h5_path"], "r") as whole:
        for name in ("raw_data", "od", "mean_spectra", "frame_counts", "delay_ps", "position_mm"):
            np.testing.assert_array_equal(actual[name][...], whole[name][...])
        assert actual["raw_data"].dtype == np.float32
        assert actual["od"].dtype == np.float64
        assert np.isposinf(actual["od"][0, 1]) and np.isneginf(actual["od"][0, 2])
        assert np.isnan(actual["od"][1]).all()
        assert actual["metadata/parent_run_id"][()].decode() == second["run_id"]
        assert json.loads(actual["metadata/scan_plan_json"][()].decode()) == plan.to_dict()
    assert result["next_point_index"] is None and result["next_shot_index"] is None
    assert len({first["run_id"], second["run_id"], result["run_id"]}) == 3
    assert digest(first["h5_path"]) == first_sha
    assert digest(second["h5_path"]) == second_sha


@pytest.mark.parametrize("change", [
    {"delay_points_ps": [0., 0., 2.]},
    {"pulses_per_point": 2},
    {"calibration_version": "fixture-calibration-v2"},
    {"real_zero_ps": .5},
])
def test_resume_plan_mismatch_is_rejected_before_creating_writer(monkeypatch, change):
    _plan, source = stopped_source()
    parent_sha = digest(source["h5_path"])
    monkeypatch.setattr(storage.tempfile, "mkdtemp", lambda **_: pytest.fail("Rejected resume created staging files"))
    with pytest.raises(ValueError, match="same scan plan"):
        storage.V0EmulatorRunWriter.resume_from(source["h5_path"], {}, expected_plan=make_plan(**change))
    assert digest(source["h5_path"]) == parent_sha


@pytest.mark.parametrize("mutation", ["counts_hole", "counts_overflow", "layout", "position", "wave", "status", "missing_plan"])
def test_resume_invalid_source_is_rejected_before_creating_writer(monkeypatch, mutation):
    plan, source = stopped_source()
    with h5py.File(source["h5_path"], "r+") as handle:
        if mutation == "counts_hole":
            handle["frame_counts"][...] = [0, 1, 0]
        elif mutation == "counts_overflow":
            handle["frame_counts"][0] = 4
        elif mutation == "layout":
            handle["metadata/raw_layout"][()] = "unknown-layout"
        elif mutation == "position":
            handle["position_mm"][0] = 1.
        elif mutation == "wave":
            handle["wavelength_nm"][0] = float("nan")
        elif mutation == "status":
            handle["metadata/run_status"][()] = "completed"
        else:
            del handle["metadata/scan_plan_json"]
    parent_sha = digest(source["h5_path"])
    monkeypatch.setattr(storage.tempfile, "mkdtemp", lambda **_: pytest.fail("Rejected resume created staging files"))
    with pytest.raises(ValueError):
        storage.V0EmulatorRunWriter.resume_from(source["h5_path"], {}, expected_plan=plan)
    assert digest(source["h5_path"]) == parent_sha


def test_resume_rejects_changed_wavelengths_and_exhausted_stopped_run(monkeypatch):
    plan, source = stopped_source()
    with pytest.raises(ValueError, match="wavelength axis"):
        storage.V0EmulatorRunWriter.resume_from(source["h5_path"], {}, expected_plan=plan,
                                               expected_wavelengths=[500., 601.])
    writer = new_writer(plan)
    for point in range(3):
        for shot in range(3):
            record(writer, point, shot)
    complete = writer.finalize("stopped")
    monkeypatch.setattr(storage.tempfile, "mkdtemp", lambda **_: pytest.fail("Exhausted resume created staging files"))
    with pytest.raises(ValueError, match="no remaining shots"):
        storage.V0EmulatorRunWriter.resume_from(complete["h5_path"], {}, expected_plan=plan)
