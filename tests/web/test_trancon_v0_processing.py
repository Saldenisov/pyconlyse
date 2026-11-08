"""Software-only checks of source counts, nonlinear order and preview/export."""

import hashlib
import sys
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

import h5py
import numpy as np
import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "web" / "backend"))

import pump_probe_v0_api as api
from pump_probe_v0_dataset import export_dat, load_payload, read_dataset, treat_dataset
from pump_probe_v0_processing import (
    OD_ALGORITHM, TRANCON_GROUPS, TRANCON_LAYOUT, V0_RAW_GROUPS, apply_recipe, calculate_raw_od,
)
from pump_probe_v0_storage import V0EmulatorRunWriter


def zip_raw(blocks):
    lines = ["500\t600"]
    for index, block in enumerate(blocks):
        lines.append(f"S_{index}")
        lines.extend("\t".join(str(x) for x in row) for row in block.reshape(-1, 2))
        lines.append("E_RAW")
    payload = BytesIO()
    with ZipFile(payload, "w") as archive:
        archive.writestr("sample.raw", "\n".join(lines))
    return payload.getvalue()


def detector_block():
    # Unequal backgrounds discriminate detector pairing and pulse-state pairing.
    values = np.array([[10, 20], [90, 80], [110, 120], [190, 180], [210, 420], [140, 130]])
    return np.repeat(values[:, :, None], 2, axis=2)


def oracle(block, bg=(0, 0)):
    b1, b2, e1, e2, o1, o2 = block.astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log10(((o1-b1-bg[0])/(e1-b1-bg[0])) /
                        ((o2-b2-bg[1])/(e2-b2-bg[1]))).mean(axis=0)


def test_disk_groups_and_shots_survive_load():
    block = detector_block()
    payload = zip_raw([block])
    dataset, kind = read_dataset("sample.zip", payload)
    preview = load_payload("sample.zip", payload)
    assert kind == "raw"
    assert preview["raw_groups"] == list(TRANCON_GROUPS)
    assert preview["raw_layout"] == TRANCON_LAYOUT
    assert preview["frame_counts"] == [2]
    assert preview["source_sha256"] == hashlib.sha256(payload).hexdigest()
    np.testing.assert_array_equal(dataset.blocks[0], block)
    np.testing.assert_allclose(dataset.od[0], oracle(block), atol=1e-15)
    for index, channel in enumerate(preview["channels"]):
        np.testing.assert_array_equal(channel["values"][0], block[index].mean(axis=0))
    b1, b2, e1, e2, o1, o2 = block.mean(axis=1)
    wrong = np.log10(((o1-b1)/(e1-b1))/((o2-b2)/(e2-b2)))
    assert np.max(np.abs(dataset.od[0] - wrong)) > .01


def test_zero_slots_require_explicit_policy_and_do_not_change_raw():
    block = np.concatenate([detector_block(), np.zeros((6, 1, 2), dtype=int)], axis=1)
    original = block.copy()
    retained, used, removed = calculate_raw_od([block], TRANCON_LAYOUT)
    assert np.isnan(retained).all()
    assert (used, removed) == ([3], [0])
    dropped, used, removed = calculate_raw_od([block], TRANCON_LAYOUT, "drop_whole_zero")
    np.testing.assert_allclose(dropped[0], oracle(block[:, :2]))
    assert (used, removed) == ([2], [1])
    np.testing.assert_array_equal(block, original)


def test_background_then_scale_replays_from_counts_without_mutation():
    block = detector_block()
    payload = zip_raw([block])
    fingerprint = hashlib.sha256(payload).hexdigest()
    operations = [{"kind": "raw_background", "counts": [7, -3]}, {"kind": "scale", "factor": -2.5}]
    dataset, preview = treat_dataset("sample.zip", payload, operations, fingerprint)
    np.testing.assert_allclose(dataset.od[0], -2.5 * oracle(block, (7, -3)), atol=1e-15)
    assert preview["operations"][0]["zero_slot_policy"] == "retain"
    assert preview["shot_selection"]["used_counts"] == [2]
    np.testing.assert_array_equal(dataset.blocks[0], block)
    assert hashlib.sha256(payload).hexdigest() == fingerprint


def test_signed_nonfinite_survive_internal_map_and_dat_export():
    # +Inf, -Inf, NaN; no abs, no clipping, no replacing infinities with NaN.
    block = np.array([[[0, 0, 2]], [[0, 0, 0]], [[0, 1, 1]],
                      [[1, 1, 1]], [[1, 0, 3]], [[1, 1, 1]]])
    od, _, _ = calculate_raw_od([block], TRANCON_LAYOUT)
    assert np.isposinf(od[0, 0]) and np.isneginf(od[0, 1]) and np.isnan(od[0, 2])
    payload = b"0\t1\n500\tinf\n600\t-inf\n700\tnan\n"
    dataset, _ = read_dataset("a.dat", payload)
    restored = np.loadtxt(StringIO(export_dat(dataset)))[1:, 1:].T
    np.testing.assert_array_equal(np.isnan(restored), np.isnan(dataset.od))
    np.testing.assert_array_equal(np.isposinf(restored), np.isposinf(dataset.od))
    np.testing.assert_array_equal(np.isneginf(restored), np.isneginf(dataset.od))
    preview = load_payload("a.dat", payload)
    assert preview["heatmap"] == [[None, None, None]]
    assert preview["nonfinite_counts"] == {"nan": 1, "positive_inf": 1, "negative_inf": 1}


def make_h5(groups=V0_RAW_GROUPS, counts=(2, 0), saved_od=123.456):
    payload = BytesIO()
    with h5py.File(payload, "w") as handle:
        handle["wavelength_nm"] = [500., 600.]
        handle["delay_ps"] = [-1., 1.]
        handle["od"] = np.full((2, 2), saved_od)
        frames = np.array([[0, 0], [1, 1], [1, 4], [0, 0], [1, 1], [1, 1]], dtype=float)
        raw = np.full((2, 6, 3, 2), np.nan)
        raw[0, :, :2] = frames[:, :, None]
        handle["raw_data"] = raw
        handle["frame_counts"] = counts
        handle.create_dataset("raw_group_names", data=np.array(groups, dtype=h5py.string_dtype()))
    return payload.getvalue()


def test_precalc_priority_and_actual_counts_exclude_only_h5_padding():
    payload = make_h5()
    source = load_payload("a.h5", payload)
    assert source["heatmap"] == [[123.456, 123.456], [123.456, 123.456]]
    assert source["frame_counts"] == [2, 0]
    dataset, preview = treat_dataset("a.h5", payload, [{"kind": "raw_od"}], source["source_sha256"])
    np.testing.assert_allclose(dataset.od[0], np.log10(4)/2, atol=1e-15)
    assert np.isnan(dataset.od[1]).all()
    assert preview["od_algorithm"] == OD_ALGORITHM
    assert preview["shot_selection"]["used_counts"] == [2, 0]
    assert "raw_background" not in source["capabilities"]


def test_unknown_h5_semantics_allow_stored_od_but_block_raw_recalculation():
    payload = make_h5(groups=tuple(reversed(V0_RAW_GROUPS)))
    source = load_payload("a.h5", payload)
    assert "scale" in source["capabilities"]
    assert "raw_od" not in source["capabilities"]
    assert "raw_background" not in source["capabilities"]
    with pytest.raises(ValueError, match="semantics are unknown"):
        treat_dataset("a.h5", payload, [{"kind": "raw_od"}], source["source_sha256"])


@pytest.mark.parametrize("counts", [(4, 0), (-1, 0), (1.5, 0)])
def test_invalid_h5_frame_counts_rejected(counts):
    with pytest.raises(ValueError, match="frame counts"):
        load_payload("a.h5", make_h5(counts=counts))


@pytest.mark.parametrize("recipe", [
    [{"kind": "scale", "factor": float("inf")}],
    [{"kind": "scale", "factor": True}],
    [{"kind": "nan_inf"}],
    [{"kind": "baseline"}],  # BG_corrSD indexed tunnel still needs native qualification.
    [{"kind": "raw_background", "counts": [1.5, 2]}],
    [{"kind": "raw_od", "zero_slot_policy": "nanmean"}],
    [{"kind": "scale", "factor": 2}, {"kind": "raw_od"}],
])
def test_unqualified_recipes_rejected(recipe):
    with pytest.raises(ValueError):
        apply_recipe(np.ones((1, 2)), [detector_block()], TRANCON_LAYOUT, recipe)


def test_writer_uses_per_shot_logs_for_live_h5_and_dat(tmp_path):
    writer = V0EmulatorRunWriter([500, 600], [0], [0], 2, {})
    first = [[0, 0], [1, 1], [1, 1], [0, 0], [1, 1], [1, 1]]
    second = [[0, 0], [1, 1], [4, 4], [0, 0], [1, 1], [1, 1]]
    np.testing.assert_allclose(writer.record_cycle(0, first, 0, 0), 0)
    np.testing.assert_allclose(writer.record_cycle(0, second, 0, 0), np.log10(4)/2)
    artifacts = writer.finalize()
    try:
        with h5py.File(artifacts["h5_path"]) as handle:
            np.testing.assert_allclose(handle["od"][:, 0], np.log10(4)/2)
            assert handle["metadata/od_algorithm"].asstr()[()] == OD_ALGORITHM
            np.testing.assert_array_equal(handle["raw_data"][0, :, 0], first)
            np.testing.assert_array_equal(handle["raw_data"][0, :, 1], second)
        np.testing.assert_allclose(np.loadtxt(artifacts["dat_path"])[1:, 1], np.log10(4)/2, atol=1e-8)
    finally:
        import shutil
        shutil.rmtree(Path(artifacts["h5_path"]).parent)


def test_api_preview_export_fingerprint_and_path_boundary_without_devices(monkeypatch, tmp_path):
    monkeypatch.setenv("PYCONLYSE_PUMP_PROBE_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(api, "_tango_proxy", lambda *_args, **_kwargs: pytest.fail("Numerics must not access devices"))
    source = tmp_path / "sample.zip"
    original = zip_raw([detector_block()])
    source.write_bytes(original)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    with app.test_client() as client:
        loaded = client.post("/api/pump-probe-v0/data/load", json={"path": str(source)}).get_json()
        request = {"path": str(source), "source_sha256": loaded["source_sha256"],
                   "operations": [{"kind": "scale", "factor": 3}]}
        preview = client.post("/api/pump-probe-v0/data/treat", json=request)
        assert preview.status_code == 200
        np.testing.assert_allclose(preview.get_json()["heatmap"][0], 3 * oracle(detector_block()), atol=1e-9)
        exported = client.post("/api/pump-probe-v0/data/treat", json={**request, "format": "dat"})
        assert exported.status_code == 200
        np.testing.assert_allclose(np.loadtxt(StringIO(exported.text))[1:, 1], 3 * oracle(detector_block()), atol=1e-15)
        assert source.read_bytes() == original
        reloaded = client.post("/api/pump-probe-v0/data/load", json={"path": str(source)}).get_json()
        assert reloaded["operations"] == []
        source.write_bytes(zip_raw([detector_block()+1]))
        stale = client.post("/api/pump-probe-v0/data/treat", json=request)
        assert stale.status_code == 400 and "reload" in stale.get_json()["error"]
        denied = client.post("/api/pump-probe-v0/data/treat", json={**request, "path": str(tmp_path.parent / "outside.dat")})
        assert denied.status_code == 400
