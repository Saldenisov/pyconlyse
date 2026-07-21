import json
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

from gui.controllers.openers import H5Opener


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from DeviceServers.cameras.hamamatsu_streak.vd2_acquisition import (
    Vd2Acquisition,
    Vd2AcquisitionConfig,
    Vd2Phase,
    Vd2AcquisitionError,
)


def _write_his(path: Path, frame_count: int, width: int = 2, height: int = 3):
    header = (
        'ScalingXScalingFile= Other,ScalingXScale=1,ScalingXUnit="nm",'
        'ScalingYScale=1,ScalingYUnit="ns",'
    ).encode("utf-8")
    first_bytes = bytearray(64)
    first_bytes[2:4] = len(header).to_bytes(2, "little")
    first_bytes[4:6] = width.to_bytes(2, "little")
    first_bytes[6:8] = height.to_bytes(2, "little")
    first_bytes[12:14] = (2).to_bytes(2, "little")
    first_bytes[14:16] = frame_count.to_bytes(2, "little")

    with path.open("wb") as handle:
        handle.write(first_bytes)
        handle.write(header)
        for frame in range(frame_count):
            pixels = np.full((height, width), frame, dtype=np.int16)
            handle.write(pixels.tobytes())
            handle.write(bytes(64))


class FakeStreak:
    def __init__(self, frame_count: int = 100):
        self.frame_count = frame_count
        self.calls = []

    def set_sequence_loops(self, value):
        self.calls.append(("loops", int(value)))
        return str(value)

    def start_sequence(self, wait=False):
        self.calls.append(("start", wait))

    def wait_for_async_idle(self):
        self.calls.append(("wait",))

    def save_current_sequence_his(self, path, overwrite=True):
        self.calls.append(("save", Path(path).name, overwrite))
        _write_his(Path(path), self.frame_count)
        return path

    def refresh_cached_state(self):
        return {"time_range": "1 us", "wavelength": "500"}

    def set_time_range(self, value):
        self.calls.append(("time_range", value))
        return value

    def set_wavelength_nm(self, value):
        self.calls.append(("wavelength", value))
        return str(value)

    def set_grating(self, value):
        self.calls.append(("grating", value))
        return str(value)

    def set_slit_width_um(self, value):
        self.calls.append(("slit", value))
        return str(value)

    def set_delay_channel(self, channel, value):
        self.calls.append((channel, value))
        return str(value)


class FakePhaseController:
    def __init__(self):
        self.calls = []

    def prepare_phase(self, phase):
        self.calls.append(("prepare", phase))

    def verify_phase(self, phase):
        self.calls.append(("verify", phase))


def test_vd2_run_writes_three_his_h5_files_and_manifest(tmp_path):
    streak = FakeStreak()
    phases = FakePhaseController()
    result = Vd2Acquisition(streak, phases).run(
        Vd2AcquisitionConfig(
            run_directory=tmp_path / "run",
            run_name="LiCl_001",
            time_range="1 us",
            wavelength_nm=500,
            grating="1",
            slit_width_um=20,
            dg645_delays={"Delay A": "10 ns"},
        )
    )

    assert [call for call in phases.calls if call[0] == "prepare"] == [
        ("prepare", Vd2Phase.NOISE),
        ("prepare", Vd2Phase.BASE),
        ("prepare", Vd2Phase.ABS),
    ]
    assert [call for call in streak.calls if call[0] == "loops"] == [
        ("loops", 100), ("loops", 100), ("loops", 100),
    ]

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["status"] == "completed"
    assert set(manifest["phases"]) == {"NOISE", "BASE", "ABS"}
    for phase in Vd2Phase:
        paths = result.phase_files[phase]
        assert paths["his"].is_file()
        assert paths["h5"].is_file()
        with h5py.File(paths["h5"], "r") as h5_file:
            assert h5_file["raw_data"].shape == (100, 2, 3)
            assert h5_file["metadata"].attrs["phase"] == phase.value
        opener = H5Opener()
        assert opener.read_critical_info(paths["h5"]).number_maps == 100
        assert opener.read_map(paths["h5"], 0)[0].data.shape == (2, 3)


def test_vd2_run_fails_when_his_frame_count_is_wrong(tmp_path):
    streak = FakeStreak(frame_count=99)
    phases = FakePhaseController()
    acquisition = Vd2Acquisition(streak, phases)
    config = Vd2AcquisitionConfig(run_directory=tmp_path / "run", run_name="LiCl_002")

    with pytest.raises(Vd2AcquisitionError, match="contains 99 frames"):
        acquisition.run(config)

    manifest = json.loads((config.run_directory / "run.json").read_text())
    assert manifest["status"] == "failed"
