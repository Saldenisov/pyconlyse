"""Exact coordinate transport; no device, service or LabVIEW execution."""

import json
import sys
from io import StringIO
from pathlib import Path

import h5py
import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web/backend"
sys.path.insert(0, str(BACKEND))

import pump_probe_v0_storage as storage
from pump_probe_v0_dataset import V0Dataset, export_dat, load_payload, read_dataset


def coordinates(base):
    """Distinct adjacent doubles and an ordered repeat collapse in old paths."""
    value = np.float64(base)
    return np.array([value, np.nextafter(value, np.inf), value,
                     np.nextafter(value, -np.inf)], dtype=np.float64)


def exact_bits(actual, expected):
    actual = np.asarray(actual, dtype=np.float64)
    np.testing.assert_array_equal(actual.view(np.uint64), expected.view(np.uint64))


@pytest.fixture
def completed_run(tmp_path, monkeypatch):
    stage = tmp_path / "run"
    stage.mkdir()
    monkeypatch.setattr(storage.tempfile, "mkdtemp", lambda **_kwargs: str(stage))
    waves = coordinates(512.1234567890123)
    delays = coordinates(-0.12345678901234567)
    positions = coordinates(50.123456789012344)
    # The fixture must distinguish both lossy implementations, not broad tolerances.
    for axis in (waves, delays, positions):
        assert axis[0] != axis[1]
        assert axis.astype(np.float32)[0] == axis.astype(np.float32)[1]
        assert round(float(axis[0]), 5) == round(float(axis[1]), 5)
    frames = np.array([[0.] * 4, [100.] * 4, [80.] * 4,
                       [0.] * 4, [100.] * 4, [40.] * 4], dtype=np.float32)
    writer = storage.V0EmulatorRunWriter(waves, delays, positions, 1, {}, run_id="axis_precision")
    try:
        for index, position in enumerate(positions):
            writer.record_cycle(index, frames, position, np.nextafter(position, np.inf))
        artifacts = writer.finalize()
    finally:
        if not writer._closed:
            writer.finalize(status="failed")
    return artifacts, waves, delays, positions, frames


def test_h5_coordinates_preserve_double_bits_and_raw_storage(completed_run):
    artifacts, waves, delays, positions, frames = completed_run
    with h5py.File(artifacts["h5_path"], "r") as handle:
        for name, expected in (("wavelength_nm", waves), ("delay_ps", delays),
                               ("position_mm", positions)):
            assert handle[name].dtype == np.dtype("float64")
            exact_bits(handle[name][...], expected)
        assert handle["raw_data"].dtype == np.dtype("float32")
        assert handle["mean_spectra"].dtype == np.dtype("float32")
        np.testing.assert_array_equal(handle["raw_data"][:, :, 0, :], np.tile(frames, (4, 1, 1)))
        np.testing.assert_array_equal(handle["mean_spectra"][...], np.tile(frames, (4, 1, 1)))


def test_writer_dat_preserves_adjacent_coordinates_and_ordered_repeats(completed_run):
    artifacts, waves, delays, _positions, _frames = completed_run
    matrix = np.loadtxt(artifacts["dat_path"])
    exact_bits(matrix[0, 1:], delays)
    exact_bits(matrix[1:, 0], waves)


@pytest.mark.parametrize("artifact_key", ["h5_path", "dat_path"])
def test_loaded_json_axes_preserve_double_bits(completed_run, artifact_key):
    artifacts, waves, delays, _positions, _frames = completed_run
    path = Path(artifacts[artifact_key])
    dataset, _kind = read_dataset(str(path), path.read_bytes())
    exact_bits(dataset.wavelengths, waves)
    exact_bits(dataset.delays, delays)
    # Exercise actual JSON encoding/decoding, not only a Python list comparison.
    response = json.loads(json.dumps(load_payload(str(path), path.read_bytes())))
    exact_bits(response["wavelengths"], waves)
    exact_bits(response["delays"], delays)


def test_dataset_dat_export_retains_all_double_digits():
    waves = coordinates(512.1234567890123)
    delays = coordinates(-0.12345678901234567)
    dataset = V0Dataset(waves, delays, np.arange(16, dtype=float).reshape(4, 4))
    matrix = np.loadtxt(StringIO(export_dat(dataset)))
    exact_bits(matrix[0, 1:], delays)
    exact_bits(matrix[1:, 0], waves)


def test_manifest_json_retains_delay_and_position_coordinates(completed_run):
    artifacts, _waves, delays, positions, _frames = completed_run
    events = [json.loads(line) for line in Path(artifacts["manifest_path"]).read_text().splitlines()]
    frames = [event for event in events if event["event"] == "frame_acquired"]
    for index in range(len(delays)):
        point = [event for event in frames if event["delay_index"] == index]
        assert len(point) == 6
        for event in point:
            exact_bits([event["delay_ps"]], delays[index:index+1])
            exact_bits([event["target_position_mm"]], positions[index:index+1])
            exact_bits([event["readback_position_mm"]], np.nextafter(positions[index:index+1], np.inf))
