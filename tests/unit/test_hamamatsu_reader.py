"""Disposable HIS fixtures for signed pixels, map selection and calibrated axes."""
import numpy as np
import pytest

from utilities.dataio import HamamatsuFileOpener
from utilities.errors.myexceptions import NoSuchFileType


def write_his(path, pixel_code=2, maps=2, *, time_table=None, time_count=None):
    comment = (
        'ScalingXType=1,ScalingXScale=1,ScalingXUnit="No unit",ScalingXScalingFile="Other",'
        'ScalingYScale=0.5,ScalingYUnit="ns",'
    ).encode("utf-8")
    if time_table is not None:
        count = len(time_table) if time_count is None else time_count
        time_field = f'ScalingYScalingFile="#{0:07d},{count:04d}"\r\n'.encode()
        offset = 64 + len(comment) + len(time_field)
        comment += time_field.replace(b"#0000000", f"#{offset:07d}".encode())
        comment += np.asarray(time_table, dtype="<f4").tobytes()
    header = bytearray(64)
    header[:2] = b"IM"
    for offset, value in [(2, len(comment)), (4, 3), (6, 2), (12, pixel_code), (14, maps)]:
        header[offset:offset + 2] = value.to_bytes(2, "little")
    dtype = {1: np.dtype("i1"), 2: np.dtype("<i2"), 3: np.dtype("<i4")}[pixel_code]
    pixels = np.array([[-1, 2, 3], [4, -5, 6]], dtype=dtype)
    content = bytes(header) + comment + pixels.tobytes()
    for index in range(1, maps):
        content += bytes(64) + (pixels + index * 10).astype(dtype).tobytes()
    path.write_bytes(content)
    return pixels.T


def test_his_uses_embedded_time_calibration_with_pixel_wavelength_axis(tmp_path):
    path = tmp_path / "camera_only.his"
    expected_pixels = write_his(path, time_table=[0.75, 1.125])
    opener = HamamatsuFileOpener()
    metadata = opener.read_critical_info(path)
    assert metadata.scaling_yunit == "ns"
    np.testing.assert_array_equal(metadata.wavelengths, [0, 1, 2])
    np.testing.assert_array_equal(metadata.timedelays, [0.75, 1.125])
    measurement, error = opener.read_map(path, 0)
    assert not error
    np.testing.assert_array_equal(measurement.timedelays, [0.75, 1.125])
    np.testing.assert_array_equal(measurement.data, expected_pixels)


def test_his_rejects_time_calibration_with_wrong_height(tmp_path):
    path = tmp_path / "bad_calibration.his"
    write_his(path, time_table=[0.75, 1.125], time_count=3)
    with pytest.raises(ValueError, match="time calibration does not match image height"):
        HamamatsuFileOpener().read_critical_info(path)


@pytest.mark.parametrize("pixel_code,bytes_per_point", [(1, 1), (2, 2), (3, 4)])
def test_his_preserves_signed_pixels_and_wavelength_time_orientation(tmp_path, pixel_code, bytes_per_point):
    path = tmp_path / "synthetic.his"
    expected = write_his(path, pixel_code)
    opener = HamamatsuFileOpener()
    metadata = opener.read_critical_info(path)
    assert metadata.bytes_per_point == bytes_per_point
    assert metadata.number_maps == 2
    assert metadata.scaling_xunit == "pixel"
    np.testing.assert_array_equal(metadata.wavelengths, [0, 1, 2])
    np.testing.assert_array_equal(metadata.timedelays, [0, 0.5])
    measurement, error = opener.read_map(path, 0)
    assert error == ""
    assert measurement.data.shape == (3, 2)
    np.testing.assert_array_equal(measurement.data, expected)
    np.testing.assert_array_equal(opener.read_map(path, 1)[0].data, expected + 10)
    np.testing.assert_array_equal(opener.read_map(path, -1)[0].data, expected)
    np.testing.assert_array_equal(opener.read_map(path, 20)[0].data, expected + 10)


def test_his_all_maps_and_pairs_read_the_same_disposable_frames(tmp_path):
    path = tmp_path / "synthetic.his"
    expected = write_his(path)
    opener = HamamatsuFileOpener()
    frames = list(opener.give_all_maps(path))
    pairs = list(opener.give_pair_maps(path))
    assert len(frames) == 2
    assert len(pairs) == 1
    for actual, reference in [(frames[0], expected), (frames[1], expected + 10),
                              (pairs[0][0], expected), (pairs[0][1], expected + 10)]:
        np.testing.assert_array_equal(actual.data, reference)


def test_his_missing_input_is_an_error_and_wrong_extension_is_rejected(tmp_path):
    opener = HamamatsuFileOpener()
    with pytest.raises(NoSuchFileType):
        opener.read_critical_info(tmp_path / "unsupported.txt")
    with pytest.raises(FileNotFoundError):
        opener.read_critical_info(tmp_path / "missing.his")
    with pytest.raises(OSError):
        opener.read_map(tmp_path / "missing.his")
