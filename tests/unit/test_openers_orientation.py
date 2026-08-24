from pathlib import Path

import numpy as np

from gui.controllers.openers.ASCIIOpener import ASCIIOpener
from gui.controllers.openers.H5Opener import H5Opener
from gui.controllers.openers.Opener import CriticalInfo


def _critical_info(path: Path, wavelengths, timedelays) -> CriticalInfo:
    return CriticalInfo(
        file_path=path,
        number_maps=1,
        timedelays_length=len(timedelays),
        wavelengths_length=len(wavelengths),
        timedelays=np.asarray(timedelays, dtype=float),
        wavelengths=np.asarray(wavelengths, dtype=float),
        scaling_yunit="ps",
    )


def test_ascii_opener_reads_current_wavelength_row_layout(tmp_path):
    wavelengths = np.asarray([500.0, 550.0])
    timedelays = np.asarray([-1.0, 0.0, 2.0])
    expected_data = np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    path = tmp_path / "OD_roundtrip.dat"
    payload = np.zeros((len(wavelengths) + 1, len(timedelays) + 1))
    payload[0, 1:] = timedelays
    payload[1:, 0] = wavelengths
    payload[1:, 1:] = expected_data
    np.savetxt(path, payload, delimiter="\t", fmt="%.6g")

    measurement, comments = ASCIIOpener().read_map(path)

    assert comments == ""
    np.testing.assert_array_equal(measurement.wavelengths, wavelengths)
    np.testing.assert_array_equal(measurement.timedelays, timedelays)
    np.testing.assert_array_equal(measurement.data, expected_data)
    assert measurement.data.shape == (len(wavelengths), len(timedelays))


def test_ascii_opener_reads_legacy_timedelay_row_layout(tmp_path):
    wavelengths = np.asarray([500.0, 550.0, 600.0])
    timedelays = np.asarray([-1.0, 2.0])
    expected_data = np.asarray([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    payload = np.zeros((len(timedelays) + 1, len(wavelengths) + 1))
    payload[0, 1:] = wavelengths
    payload[1:, 0] = timedelays
    payload[1:, 1:] = expected_data.transpose()
    path = tmp_path / "legacy_OD.dat"
    np.savetxt(path, payload, delimiter="\t", fmt="%.6g")

    measurement, comments = ASCIIOpener().read_map(path)

    assert comments == ""
    np.testing.assert_array_equal(measurement.wavelengths, wavelengths)
    np.testing.assert_array_equal(measurement.timedelays, timedelays)
    np.testing.assert_array_equal(measurement.data, expected_data)
    assert measurement.data.shape == (len(wavelengths), len(timedelays))


def test_h5_opener_unexpected_shape_logs_path_without_name_error(caplog):
    path = Path("unexpected-shape.h5")
    info = _critical_info(path, wavelengths=[500.0, 550.0], timedelays=[0.0, 1.0, 2.0])
    data = np.zeros((4, 5))

    with caplog.at_level("ERROR"):
        result = H5Opener()._reorient_data2d(data, info)

    assert result is data
    assert "unexpected-shape.h5" in caplog.text
    assert "unexpected raw_data 2D shape (4, 5)" in caplog.text
