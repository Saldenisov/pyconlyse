import re
import struct

import numpy as np
import pytest

from utilities.dataio.hamamatsu_his_calibration import embed_native_axes


@pytest.mark.parametrize(("extension", "count"), [("img", 1), ("his", 2)])
def test_axes_are_native_tables_and_preserve_image_payload(tmp_path, extension, count):
    path = tmp_path / f"recording.{extension}"
    text = (
        b'ScalingXType=1,ScalingXScale=2,ScalingXUnit="",ScalingXScalingFile="Other",'
        b'ScalingYType=2,ScalingYScale=1,ScalingYUnit="us",ScalingYScalingFile="#%07d,0003"'
    )
    times = [0.5, 0.75, 1.25]
    table = struct.pack("<3f", *times)
    header = text % (64 + len(text % 0) + (18 if extension == "img" else 0))
    if extension == "his":
        header += table
    fixed = bytearray(64)
    struct.pack_into("<2s7H", fixed, 0, b"IM", len(header), 3, 3, 0, 0, 2, 0 if extension == "img" else count)
    payload = struct.pack("<9H", *range(9))
    if count == 2:
        payload += bytes(64) + struct.pack("<9H", *range(9, 18))
    path.write_bytes(fixed + header + payload + (table if extension == "img" else b""))

    wavelengths = [435.0, 490.0, 550.0]
    embed_native_axes(path, wavelengths, calibration_id="Hg-test", valid_columns=(0, 2), zero_time=True)

    raw = path.read_bytes()
    stop = 64 + struct.unpack_from("<H", raw, 2)[0]
    tables = {}
    for key, offset, length in re.findall(rb'Scaling([XY])ScalingFile="#(\d+),(\d+)"', raw[64:stop]):
        offset, length = int(offset), int(length)
        if extension == "img":
            assert stop + len(payload) <= offset < offset + length * 4 <= len(raw)
        else:
            assert 64 <= offset < offset + length * 4 <= stop
        tables[key.decode()] = np.frombuffer(raw, dtype="<f4", count=length, offset=offset).tolist()
    assert tables == {"X": wavelengths, "Y": [0, 0.25, 0.75]}
    assert raw[stop:stop + len(payload)] == payload
    embed_native_axes(path, wavelengths, calibration_id="Hg-test", valid_columns=(0, 2), zero_time=True)
    assert path.read_bytes() == raw
