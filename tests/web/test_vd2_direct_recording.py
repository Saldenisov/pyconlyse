import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web" / "backend"))

from vd2_direct_recording import recording_axes, _write_sequence
from vd2_his_timing import read_frame_intervals_ms
from vd2_measurement_protocol import PhaseRequest, Vd2ProtocolError
from vd2_sequence_processing import process_saved_sequence
from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener


def configuration():
    return {
        "time_range": "1 us",
        "camera": {"model": "C13440-20CU", "serial": "S/N: 303256", "roi": [352, 1632, 516, 1532, 2, 2]},
        "kymera_device": "manip/CR/ANDOR_KYMERA1",
        "optics": {"grating": 3, "wavelength_nm": 550.0, "lines_per_mm": 150.0, "blaze_wavelength_nm": 500.0,
                   "exit_mirror": "Front", "focus_mirror": 300, "turret": 1, "side_entry_iris": 50},
    }


@pytest.mark.parametrize("rate", [5, 10])
def test_direct_native_sequence_converts_unsigned_counts_calibration_and_timestamps(tmp_path, rate):
    path = tmp_path / "BASE.his"
    axes = recording_axes(configuration())
    frame = np.arange(508 * 640, dtype=np.uint16).reshape(508, 640)
    stamps = [73, 74, 75]
    timestamps = [1_000_000 + i * (1_000_000 // rate) for i in range(3)]
    _write_sequence(path, 3, axes, iter(zip(timestamps, stamps, [frame] * 3)), rate)
    assert read_frame_intervals_ms(path, 3) == [1000 / rate] * 2
    info = HamamatsuFileOpener().read_critical_info(path)
    assert info.timedelays[0] == 0 and info.scaling_yunit == "us"
    wavelengths, identity, columns = axes[1]
    request = PhaseRequest("BASE", 3, str(tmp_path), "test", str(path),
                           spectral_axis_nm=wavelengths, spectral_calibration_id=identity,
                           spectral_valid_columns=columns, direct_rate_hz=rate)
    result = process_saved_sequence(request)
    with h5py.File(result["h5_path"], "r") as converted:
        np.testing.assert_array_equal(converted["raw_data"][2], frame.T)
        np.testing.assert_array_equal(converted["camera_timestamp_ms"][:], np.asarray(timestamps) / 1000)
        assert converted["metadata"].attrs["trigger_rate_hz"] == rate


def test_direct_rejects_unverified_detector_or_missing_frame(tmp_path):
    settings = configuration()
    settings["camera"]["serial"] = "303257"
    with pytest.raises(Vd2ProtocolError, match="camera geometry"):
        recording_axes(settings)
    frame = np.zeros((508, 640), dtype=np.uint16)
    with pytest.raises(Vd2ProtocolError, match="frame 2"):
        _write_sequence(tmp_path / "BRUIT.his", 2, recording_axes(configuration()),
                        iter([(1000, 1, frame), (201000, 3, frame)]), 5)
