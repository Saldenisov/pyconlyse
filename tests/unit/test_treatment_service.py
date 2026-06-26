import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from treatment_service import TreatmentDataService
import treatment_service as treatment_service_module


class FakeOpener:
    def __init__(self, measurements):
        self._measurements = list(measurements)
        self.paths = {}

    def read_map(self, file_path, map_index):
        return self._measurements[map_index], ""

    def give_all_maps(self, file_path):
        return list(self._measurements)


class FakePairOpener:
    def __init__(self, pairs):
        self._pairs = list(pairs)
        self.paths = {}

    def give_pair_maps(self, file_path):
        return list(self._pairs)


class FakeAverageOpener:
    def __init__(self, average_data):
        self._average_data = np.asarray(average_data, dtype=float)
        self.paths = {}

    def average_map(self, file_path):
        return np.array(self._average_data, copy=True)


@pytest.fixture
def service():
    return TreatmentDataService()


def _measurement(data, wavelengths=None, timedelays=None, time_scale="ps"):
    array = np.asarray(data, dtype=float)
    return SimpleNamespace(
        data=array,
        wavelengths=np.asarray(
            wavelengths if wavelengths is not None else np.arange(array.shape[0], dtype=float),
            dtype=float,
        ),
        timedelays=np.asarray(
            timedelays if timedelays is not None else np.arange(array.shape[1], dtype=float),
            dtype=float,
        ),
        time_scale=time_scale,
    )


def _critical_info(file_path, number_maps, wavelengths, timedelays):
    return SimpleNamespace(
        file_path=file_path,
        number_maps=number_maps,
        wavelengths=np.asarray(wavelengths, dtype=float),
        timedelays=np.asarray(timedelays, dtype=float),
        wavelengths_length=len(wavelengths),
        timedelays_length=len(timedelays),
        scaling_yunit="ps",
        header="fake header",
    )


def test_parse_average_ranges_supports_desktop_formats(service):
    parsed = service._parse_average_ranges("500+-10; 600 5; 700")

    assert parsed == [(500.0, 10.0), (600.0, 5.0), (700.0, 3.0)]


def test_normalize_bounds_swaps_and_clamps_invalid_values(service):
    start, end = service._normalize_bounds(8, 2, 10)

    assert (start, end) == (2, 8)

    start, end = service._normalize_bounds(-5, 99, 6)

    assert (start, end) == (0, 5)


def test_get_selection_view_returns_heatmap_kinetics_and_spectrum(service, monkeypatch):
    file_path = Path("/tmp/selection_unit.dat")
    measurement = _measurement(
        [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
        wavelengths=[500.0, 550.0, 600.0],
        timedelays=[1.0, 2.0],
    )
    info = _critical_info(file_path, 1, [500.0, 550.0, 600.0], [1.0, 2.0])
    opener = FakeOpener([measurement])
    opener.paths[file_path] = info

    monkeypatch.setattr(service, "_resolve_active_path", lambda state: ("ABS", file_path))
    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    payload = service.get_selection_view(
        {
            "active_data_type": "ABS",
            "map_index": 0,
            "selection": {"x1": 1, "x2": 2, "y1": 0, "y2": 1},
            "paths": {"ABS": str(file_path)},
        }
    )

    assert payload["active_data_type"] == "ABS"
    assert payload["cursors"]["x1"] == 1
    assert payload["cursors"]["x2"] == 2
    assert payload["kinetics"]["y"] == [3.0, 4.0]
    assert payload["spectrum"]["y"] == [1.0, 3.0, 5.0]
    assert payload["heatmap"]["z"] == [[1.0, 3.0, 5.0], [2.0, 4.0, 6.0]]


def test_export_selection_average_rejects_invalid_range_text(service, monkeypatch):
    file_path = Path("/tmp/export_unit.dat")
    measurement = _measurement(
        [[1.0, 2.0], [3.0, 4.0]],
        wavelengths=[500.0, 550.0],
        timedelays=[1.0, 2.0],
    )
    info = _critical_info(file_path, 1, [500.0, 550.0], [1.0, 2.0])
    opener = FakeOpener([measurement])
    opener.paths[file_path] = info

    monkeypatch.setattr(service, "_resolve_active_path", lambda state: ("ABS", file_path))
    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    with pytest.raises(ValueError, match="Invalid range"):
        service.export_selection_average(
            {"active_data_type": "ABS", "map_index": 0, "paths": {"ABS": str(file_path)}},
            "kinetics",
            "500 bad extra",
        )


def test_analyze_sam_cleaning_filters_by_angle_and_surface(service, monkeypatch):
    file_path = Path("/tmp/sam_unit.dat")
    measurements = [
        _measurement([[1.0, 1.0], [1.0, 1.0]]),
        _measurement([[2.0, 2.0], [2.0, 2.0]]),
        _measurement([[1.0, 0.0], [1.0, 0.0]]),
    ]
    info = _critical_info(file_path, 3, [500.0, 550.0], [1.0, 2.0])
    opener = FakeOpener(measurements)
    opener.paths[file_path] = info

    monkeypatch.setattr(service, "_resolve_active_path", lambda state: ("ABS", file_path))
    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    summary = service.analyze_sam_cleaning(
        "session-a",
        {"active_data_type": "ABS", "paths": {"ABS": str(file_path)}},
        angle_threshold=20.0,
        surface_threshold=50.0,
    )

    assert summary["file_path"] == str(file_path)
    assert summary["original_measurements"] == 3
    assert summary["cleaned_measurements"] == 1
    assert summary["removed_by_angle"] == 1
    assert summary["removed_by_surface"] == 1
    assert summary["kept_indices"] == [0]
    assert 30.0 < summary["sam_angle_max"] < 40.0


def test_analyze_sam_cleaning_reuses_current_cleaned_state_until_reset(service, monkeypatch):
    file_path = Path("/tmp/sam_iterative_unit.dat")
    measurements = [
        _measurement([[1.0, 1.0], [1.0, 1.0]]),
        _measurement([[1.0, 1.0], [1.0, 1.0]]),
        _measurement([[1.0, 1.0], [1.0, 1.0]]),
        _measurement([[0.0, 2.0], [0.0, 2.0]]),
    ]
    info = _critical_info(file_path, 4, [500.0, 550.0], [1.0, 2.0])
    opener = FakeOpener(measurements)
    opener.paths[file_path] = info

    monkeypatch.setattr(service, "_resolve_active_path", lambda state: ("ABS", file_path))
    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    first = service.analyze_sam_cleaning(
        "session-iterative",
        {"active_data_type": "ABS", "paths": {"ABS": str(file_path)}},
        angle_threshold=20.0,
        surface_threshold=10.0,
    )
    second = service.analyze_sam_cleaning(
        "session-iterative",
        {"active_data_type": "ABS", "paths": {"ABS": str(file_path)}},
        angle_threshold=20.0,
        surface_threshold=10.0,
    )
    reset_summary = service.reset_sam_cleaning(
        "session-iterative",
        {"active_data_type": "ABS", "paths": {"ABS": str(file_path)}},
    )
    after_reset = service.analyze_sam_cleaning(
        "session-iterative",
        {"active_data_type": "ABS", "paths": {"ABS": str(file_path)}},
        angle_threshold=20.0,
        surface_threshold=10.0,
    )

    assert first["source_measurements"] == 4
    assert first["cleaned_measurements"] == 3
    assert first["state_updated"] is True
    assert second["source_measurements"] == 3
    assert second["original_measurements"] == 4
    assert reset_summary["reset"] is True
    assert reset_summary["discarded_measurements"] == 3
    assert after_reset["source_measurements"] == 4


def test_get_cleaning_view_returns_cleaned_kinetics(service, monkeypatch):
    file_path = Path("/tmp/sam_view_unit.dat")
    measurements = [
        _measurement([[1.0, 3.0], [5.0, 7.0]], timedelays=[10.0, 20.0]),
        _measurement([[2.0, 4.0], [6.0, 8.0]], timedelays=[10.0, 20.0]),
    ]
    info = _critical_info(file_path, 2, [500.0, 550.0], [10.0, 20.0])
    opener = FakeOpener(measurements)
    opener.paths[file_path] = info

    monkeypatch.setattr(service, "_resolve_active_path", lambda state: ("ABS", file_path))
    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    session_state = {
        "active_data_type": "ABS",
        "paths": {"ABS": str(file_path)},
        "path_sources": {"ABS": "smb://10.20.30.202/e/DATA_VD2/20260127/water/ABS12886.his"},
    }
    service.analyze_sam_cleaning(
        "session-cleaning-view",
        session_state,
        angle_threshold=180.0,
        surface_threshold=100.0,
    )
    view = service.get_cleaning_view("session-cleaning-view", session_state, trace_limit=1)

    assert view["cleaned_state"] is True
    assert view["source_file_path"] == session_state["path_sources"]["ABS"]
    assert view["current_measurements"] == 2
    assert view["shown_measurements"] == 1
    assert view["x"] == [10.0, 20.0]
    assert view["average"] == [3.5, 5.5]
    assert view["y_axis_type"] == "log"


def test_save_sam_cleaned_h5_defaults_to_source_folder_and_stem(
    service, monkeypatch, tmp_path
):
    if treatment_service_module.h5py is None:
        pytest.skip("h5py is not available")

    cached_path = tmp_path / "cache" / "ABS12886.his"
    cached_path.parent.mkdir()
    cached_path.write_text("fake", encoding="ascii")
    source_path = tmp_path / "20260127" / "water" / "ABS12886.his"
    source_path.parent.mkdir(parents=True)

    measurements = [
        _measurement([[1.0, 1.0], [1.0, 1.0]]),
        _measurement([[2.0, 2.0], [2.0, 2.0]]),
    ]
    info = _critical_info(cached_path, 2, [500.0, 550.0], [1.0, 2.0])
    opener = FakeOpener(measurements)
    opener.paths[cached_path] = info
    written = {}

    def fake_write_cleaned_h5(**kwargs):
        written.update(kwargs)
        Path(kwargs["output_path"]).write_bytes(b"h5")

    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))
    monkeypatch.setattr(service, "_write_cleaned_h5", fake_write_cleaned_h5)

    summary = service.save_sam_cleaned_h5(
        "session-save-cleaned",
        {
            "active_data_type": "ABS",
            "paths": {"ABS": str(cached_path)},
            "path_sources": {"ABS": str(source_path)},
        },
        angle_threshold=180.0,
        surface_threshold=100.0,
    )

    assert summary["source_file_path"] == str(source_path)
    assert summary["output_path"] == str(source_path.parent / "ABS12886.h5")
    assert summary["compression"] == "gzip"
    assert summary["compression_level"] == 9
    assert written["output_path"] == source_path.parent / "ABS12886.h5"


def test_convert_file_to_h5_uses_gzip_level_9(service, monkeypatch, tmp_path):
    h5py = treatment_service_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")

    source_path = tmp_path / "ABS12886.his"
    source_path.write_bytes(b"fake his")
    output_path = tmp_path / "ABS12886.h5"
    measurements = [
        _measurement([[1.0, 2.0], [3.0, 4.0]], [500.0, 550.0], [1.0, 2.0]),
        _measurement([[2.0, 3.0], [4.0, 5.0]], [500.0, 550.0], [1.0, 2.0]),
    ]
    info = _critical_info(source_path, 2, [500.0, 550.0], [1.0, 2.0])
    opener = FakeOpener(measurements)
    opener.paths[source_path] = info

    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (opener, info))

    summary = service.convert_file_to_h5(source_path, output_path)

    assert summary["output_path"] == str(output_path)
    with h5py.File(output_path, "r") as h5_file:
        raw_data = h5_file["raw_data"]
        assert raw_data.compression == "gzip"
        assert raw_data.compression_opts == 9
        assert h5_file["metadata"].attrs["compression"] == "gzip"
        assert h5_file["metadata"].attrs["compression_level"] == 9

    overwrite_summary = service.convert_file_to_h5(output_path, output_path)
    assert overwrite_summary["output_path"] == str(output_path)
    with h5py.File(output_path, "r") as h5_file:
        raw_data = h5_file["raw_data"]
        assert raw_data.compression == "gzip"
        assert raw_data.compression_opts == 9


def test_calc_abs_supports_his_mode_with_abs_base_noise_pairs(service, monkeypatch, tmp_path):
    data_path = tmp_path / "his_source.his"
    data_path.write_text("fake", encoding="ascii")

    pair_opener = FakePairOpener(
        [
            (
                _measurement([[2.0, 2.0], [2.0, 2.0]]),
                _measurement([[4.0, 4.0], [4.0, 4.0]]),
            ),
            (
                _measurement([[3.0, 3.0], [3.0, 3.0]]),
                _measurement([[6.0, 6.0], [6.0, 6.0]]),
            ),
        ]
    )
    info = _critical_info(data_path, 4, [500.0, 550.0], [1.0, 2.0])

    monkeypatch.setattr(service, "_get_opener_and_info", lambda path: (pair_opener, info))

    payload = service.calc_abs(
        "session-his",
        {
            "exp_type": "HIS",
            "calc_mode": "averaged",
            "first_map_with_electrons": True,
            "paths": {"ABS+BASE+NOISE": str(data_path)},
        },
    )

    expected = np.log10(np.full((2, 2), 2.0, dtype=float))
    assert payload["shape"] == [2, 2]
    assert np.allclose(np.asarray(payload["sample"], dtype=float), expected)

    runtime = service.runtime_status("session-his")
    assert runtime["result_ready"] is True
    assert runtime["result_shape"] == (2, 2)


def test_calc_abs_his_noise_uses_noise_average_and_pair_order(
    service, monkeypatch, tmp_path
):
    data_path = tmp_path / "his_abs_base.his"
    noise_path = tmp_path / "noise_reference.his"
    data_path.write_text("fake", encoding="ascii")
    noise_path.write_text("fake", encoding="ascii")

    pair_opener = FakePairOpener(
        [
            (
                _measurement([[9.0, 9.0], [9.0, 9.0]]),
                _measurement([[3.0, 3.0], [3.0, 3.0]]),
            ),
            (
                _measurement([[15.0, 15.0], [15.0, 15.0]]),
                _measurement([[5.0, 5.0], [5.0, 5.0]]),
            ),
        ]
    )
    noise_opener = FakeAverageOpener([[1.0, 1.0], [1.0, 1.0]])
    data_info = _critical_info(data_path, 4, [500.0, 550.0], [1.0, 2.0])
    noise_info = _critical_info(noise_path, 2, [500.0, 550.0], [1.0, 2.0])

    def fake_get_opener_and_info(path):
        if path == data_path:
            return pair_opener, data_info
        if path == noise_path:
            return noise_opener, noise_info
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(service, "_get_opener_and_info", fake_get_opener_and_info)

    payload = service.calc_abs(
        "session-his-noise",
        {
            "exp_type": "HIS+NOISE",
            "calc_mode": "individual",
            "first_map_with_electrons": False,
            "paths": {
                "ABS+BASE": str(data_path),
                "NOISE": str(noise_path),
            },
        },
    )

    expected_value = (np.log10(4.0) + np.log10(3.5)) / 2.0
    expected = np.full((2, 2), expected_value, dtype=float)
    assert payload["shape"] == [2, 2]
    assert np.allclose(np.asarray(payload["sample"], dtype=float), expected)

    runtime = service.runtime_status("session-his-noise")
    assert runtime["noise_ready"] is True
    assert runtime["result_ready"] is True


def test_save_result_writes_dat_to_smb_folder(service, monkeypatch, tmp_path):
    abs_path = tmp_path / "abs.his"
    base_path = tmp_path / "base.his"
    noise_path = tmp_path / "bruit.his"
    for file_path in (abs_path, base_path, noise_path):
        file_path.write_text("fake", encoding="ascii")

    abs_opener = FakeAverageOpener([[2.0, 2.0], [2.0, 2.0]])
    base_opener = FakeAverageOpener([[4.0, 4.0], [4.0, 4.0]])
    noise_opener = FakeAverageOpener([[1.0, 1.0], [1.0, 1.0]])
    info = _critical_info(abs_path, 1, [500.0, 550.0], [1.0, 2.0])

    def fake_get_opener_and_info(path):
        if path == abs_path:
            return abs_opener, info
        if path == base_path:
            return base_opener, info
        if path == noise_path:
            return noise_opener, info
        raise AssertionError(f"Unexpected path {path}")

    copied = {}

    def fake_copy_local_file_to_smb(local_path, smb_path):
        copied["smb_path"] = smb_path
        copied["payload"] = Path(local_path).read_text(encoding="utf-8")
        return len(copied["payload"].encode("utf-8"))

    monkeypatch.setattr(service, "_get_opener_and_info", fake_get_opener_and_info)
    monkeypatch.setattr(
        treatment_service_module,
        "copy_local_file_to_smb",
        fake_copy_local_file_to_smb,
    )

    service.calc_abs(
        "session-save-smb",
        {
            "exp_type": "ABS+BASE+NOISE",
            "paths": {
                "ABS": str(abs_path),
                "BASE": str(base_path),
                "NOISE": str(noise_path),
            },
        },
    )
    saved = service.save_result(
        "session-save-smb",
        {
            "save_folder": "smb://10.20.30.202/e/DATA_VD2/20260127",
            "save_file_name": "water_test",
        },
    )

    assert saved["save_path"] == "smb://10.20.30.202/e/DATA_VD2/20260127/water_test.dat"
    assert copied["smb_path"] == saved["save_path"]
    assert "500.0000" in copied["payload"]
    assert "0.4771" in copied["payload"]
