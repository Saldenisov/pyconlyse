import importlib
import json
from pathlib import Path

import numpy as np
import pytest

h5py = pytest.importorskip("h5py")


@pytest.fixture
def gamma_run(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4] / "Gamma-spectrometer"))
    return importlib.import_module("avantes_run")


def test_blank_anchors_correct_only_bracketed_rows_and_preserve_raw_counts(tmp_path, gamma_run):
    wavelengths = (np.array([350, 400]), np.array([349, 376, 401]))
    run = gamma_run.AvantesRun.create(tmp_path / "run.h5", wavelengths, ["A", "B"], 100, {}, {})
    raw1 = np.array([1200, 3600], dtype=float)
    raw2 = np.array([5000, 5300, 5700], dtype=float)
    sample = np.array([0.2, 0.4])
    for timestamp, drift in [(0, 0), (15, 0.15), (35, 0.25), (55, 0.05), (70, 0.05)]:
        measured_od = sample + drift
        run.append(timestamp, 100 + timestamp, raw1, raw2, measured_od, measured_od,
                   {"channels": [{"averages": 40, "integration_ms": 12}, {"averages": 40}],
                    "channel_ok": [True, True]})

    blank = dict(ch1=raw1, ch2=raw2, metadata={"utc_s": 98})
    run.add_blank(0, [blank], np.zeros(2), initial=True)
    schedule = dict(delay_minutes=0.5, requested_utc_s=100, due_utc_s=130, auto_capture=False)
    run.append_event("blank_scheduled", 100, **schedule)
    run.add_blank(30, [dict(blank, metadata={"utc_s": 130, "blank_schedule": schedule})], np.full(2, 0.3))
    run.add_blank(60, [dict(blank, metadata={"utc_s": 160})], np.zeros(2))
    recalculated = run.recalculate()

    with h5py.File(run.path, "r") as file:
        entry = file["entry"]
        assert entry.attrs["NX_class"] == "NXentry" and entry.attrs["default"] == "od_live"
        assert entry["raw_ch2/data"].id == entry["instrument/detector_2/data"].id
        assert list(entry["od_live"].attrs["axes"]) == ["time", "wavelength"]
        assert entry["od_live/od"].dims[1][0].id == entry["raw_ch1/wavelength"].id
        np.testing.assert_allclose(file[f"{recalculated}/data/od"][:4], np.tile(sample, (4, 1)))
        assert np.isnan(file[f"{recalculated}/data/od"][4]).all()
        prior = entry["processing/000001_blank_correction/data/od"]
        assert np.isnan(prior[2:]).all()
        assert entry["processing/000002_blank_correction/data/od"].id != file[f"{recalculated}/data/od"].id
        np.testing.assert_array_equal(entry["raw_ch2/data"][4], raw2)
        np.testing.assert_allclose(entry["od_live/od"][4], sample + 0.05)
        assert entry["instrument/detector_1/averages_set"][4] == 40
        assert entry["instrument/detector_1/count_time_set"][4] == 0.012
        assert json.loads(entry["acquisition/metadata_json"][4])["channels"][0]["averages"] == 40
        anchor = entry["blanks/00000001"]
        assert anchor["requested_delay"][()] == 30
        assert anchor["capture_time_utc"][()] == anchor["scheduled_time_utc"][()] == 130

    run.append(80, 180, raw1, None, None, None, {"channel_ok": [True, False]})
    _, corrected, _ = run.view("od_corrected")
    assert len(corrected) == 6 and np.isnan(corrected[-2:]).all()
    assert importlib.import_module("avantes_analysis").validate_schema(run) == 6

    _, displayed, times = run.view(limit=2)
    assert len(displayed) <= 2 and times[-1] == 80
    _, _, times = run.view(time_range=(15, 35))
    np.testing.assert_array_equal(times, [15, 35])


def test_od_maps_channels_by_wavelength_and_masks_invalid_detector_pixels(gamma_run):
    wavelengths = np.array([300, 400, 500, 600]), np.array([350, 450, 550])
    dark = np.ones(4), np.ones(3)
    reference = np.full(4, 101), np.full(3, 101)
    block = {
        "ch1": np.array([11, 11, 11, 11]), "ch2": np.array([101, 101, 101]),
        "metadata": {"readout": {"0": {"saturated_pixels": [2]}}},
    }
    od = gamma_run.optical_density(*gamma_run.valid_counts(block), reference, dark, wavelengths)
    np.testing.assert_allclose(od, [np.nan, 1.0, np.nan, np.nan])
    assert block["ch1"][2] == 11


def test_mcr_removes_independent_signed_blank_drift_and_records_provenance(tmp_path, gamma_run):
    pytest.importorskip("pymcr")
    analysis = importlib.import_module("avantes_analysis")
    wavelength = np.linspace(350, 680, 45)
    counts = np.full(len(wavelength), 1200.0)
    run = gamma_run.AvantesRun.create(tmp_path / "mcr.h5", (wavelength, wavelength), ["A", "B"], 100, {}, {})
    g = lambda center: np.exp(-((wavelength - center) / 35) ** 2)
    spectra = np.stack((g(405) - 0.4 * g(480), 0.8 * g(580) - 0.2 * g(510)))
    amplitudes = np.stack((np.linspace(1, 0, 20), np.linspace(0, 0.9, 20)), axis=1)
    sample = amplitudes @ spectra
    drift_profile = 0.26 * g(405) + 0.14 * g(460)
    times = np.arange(len(sample))
    scale = np.interp(times, [0, 7, 19], [0, 1, 0.6])
    for t, expected, drift_scale in zip(times, sample, scale):
        measured = expected + drift_scale * drift_profile
        run.append(t, 100 + t, counts, counts, measured, measured, {})
    for t, drift_scale in ((0, 0), (7, 1), (19, 0.6)):
        run.add_blank(t, [dict(ch1=counts, ch2=counts, metadata={"utc_s": 100 + t})],
                      drift_scale * drift_profile, initial=t == 0)

    path = analysis.fit_mcr(run, 2, max_iter=35, wavelength_range=(350, 650), signed_spectra=True)
    result = analysis.read_mcr(run)
    assert result["path"] == path
    assert result["relative_residual"] < 1e-6
    assert np.min(result["spectra"]) < -0.05
    assert np.min(result["amplitudes"]) >= 0
    with h5py.File(run.path, "r") as file:
        result_group = file[path]
        indices = result_group["source_wavelength_index"][:]
        np.testing.assert_allclose(result_group["data/fitted_od"][:], sample[:, indices], atol=1e-6)
        np.testing.assert_allclose(file[result["source"]][:], sample, atol=1e-12)
        reconstructed = result_group["data/fitted_od"][:] + result_group["data/residual_od"][:]
        np.testing.assert_allclose(reconstructed, sample[:, indices], atol=1e-12)
    assert analysis.validate_schema(run) == len(times)
    run.recalculate()
    assert analysis.read_mcr(run)["stale"]
    default_path = analysis.fit_mcr(run, 2, max_iter=15)
    default = analysis.read_mcr(run, default_path)
    assert not default["stale"] and np.min(default["spectra"]) >= 0 and np.min(default["amplitudes"]) >= 0
    with h5py.File(run.path, "r") as file:
        assert file[path]["parameters/signed_spectra"][()]
        assert not file[default_path]["parameters/signed_spectra"][()]


def test_dose_follows_irradiation_markers_and_preserves_geometry(tmp_path, gamma_run):
    grid = np.array([300, 350])
    setup = dict(dose_rate_gy_h=72, irradiating_at_start=True, window_diameter_mm=8,
                 path_length_mm=10, sample_volume_ml=2.7)
    run = gamma_run.AvantesRun.create(tmp_path / "dose.h5", (grid, grid), ["A", "B"], 100,
                                     {"exposure": setup}, {})
    for t in (0, 15, 30, 45, 75):
        if t == 30:
            run.mark_irradiation(False, 120)
        if t == 75:
            run.mark_irradiation(True, 160)
        run.append(t, 100 + t, grid, grid, grid / 1000, grid / 1000, {})
    volume, filled = run.sample_volumes()
    assert volume == pytest.approx(0.5026548246)
    assert filled == 2.7
    blank = dict(ch1=grid, ch2=grid, metadata={"utc_s": 100})
    run.add_blank(0, [blank], np.zeros(2), initial=True)
    run.add_blank(75, [dict(blank, metadata={"utc_s": 175})], np.ones(2))
    with h5py.File(run.path, "r") as file:
        entry = file["entry"]
        np.testing.assert_allclose(entry["acquisition/dose"][:], [0, 0.3, 0.4, 0.4, 0.7])
        np.testing.assert_allclose(entry["processing/000001_blank_correction/anchor_dose"][:], [0, 0.7])
        assert entry["lamp_monitor/data"].id == entry["raw_ch2/data"].id


def test_v1_upgrade_keeps_the_source_and_recorded_od(tmp_path, gamma_run):
    old_path = tmp_path / "v1.h5"
    with h5py.File(old_path, "w") as old:
        old.attrs.update(format="avantes-gamma", version=1, serials_json='["A", "B"]',
                         started_utc_s=100, settings_json="{}")
        old.create_dataset("wavelength_nm/ch1", data=[350, 400])
        old.create_dataset("wavelength_nm/ch2", data=[348, 380, 410])
        rows = old.create_group("measurements")
        rows.attrs["committed_rows"] = 2
        for name, values in {
            "time_s": [0, 5], "utc_s": [100, 105], "ch1_counts": [[10, 20], [8, 18]],
            "ch2_counts": [[30, 40, 50], [29, 39, 49]], "od_raw": [[0, 0], [0.2, 0.3]],
            "od_delta": [[0, 0], [0.2, 0.3]], "od_corrected": [[0, 0], [0.1, 0.2]],
        }.items():
            rows.create_dataset(name, data=values)
        rows.create_dataset("metadata_json", data=["{}", "{}"])
        old.create_group("calibration")
        old.create_dataset("events_json", data=['{"event":"start"}'])
        for i in range(2):
            blank = old.create_group(f"blanks/{i:08d}")
            blank.attrs.update(initial=i == 0, time_s=5 * i)
            blank.create_dataset("ch1_counts", data=[[10, 20]])
            blank.create_dataset("ch2_counts", data=[[30, 40, 50]])
            blank.create_dataset("metadata_json", data=[json.dumps({"utc_s": 98 + 7 * i})])
            blank.create_dataset("od_raw", data=[0.1 * i, 0.1 * i])

    original = old_path.read_bytes()
    old = gamma_run.AvantesRun(old_path)
    np.testing.assert_allclose(old.view("od_corrected")[1][-1], [0.1, 0.2])
    upgraded = old.upgrade(tmp_path / "v2.h5")
    assert old_path.read_bytes() == original
    assert upgraded.schema_version() == 2
    np.testing.assert_allclose(upgraded.view("od_corrected")[1][-1], [0.1, 0.2])
    with h5py.File(upgraded.path, "r") as file:
        np.testing.assert_array_equal(file["entry/raw_ch2/data"][1], [29, 39, 49])
        np.testing.assert_allclose(file["entry/od_live/od"][1], [0.2, 0.3])
    assert importlib.import_module("avantes_analysis").validate_schema(upgraded) == 2
