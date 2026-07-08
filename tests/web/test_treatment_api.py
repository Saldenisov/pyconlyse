import json
import sys
import time
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

import numpy as np
import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from folder_api import folder_api
import folder_api as folder_api_module
import treatment_api as treatment_api_module
from treatment_api import session_store, treatment_api


def _write_dat(file_path, data, wavelengths=None, timedelays=None):
    data = np.asarray(data, dtype=float)
    wavelengths = np.asarray(wavelengths if wavelengths is not None else [500, 600], dtype=float)
    timedelays = np.asarray(timedelays if timedelays is not None else [1, 2], dtype=float)
    if data.shape != (len(wavelengths), len(timedelays)):
        raise ValueError(
            f"data shape {data.shape} does not match "
            f"(len(wavelengths), len(timedelays))={(len(wavelengths), len(timedelays))}"
        )
    payload = np.zeros((len(timedelays) + 1, len(wavelengths) + 1), dtype=float)
    payload[0, 1:] = wavelengths
    payload[1:, 0] = timedelays
    payload[1:, 1:] = data.transpose()
    np.savetxt(file_path, payload, delimiter="\t", fmt="%.4f")


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


def _critical_info(file_path, number_maps, wavelengths=None, timedelays=None):
    wavelengths = np.asarray(wavelengths if wavelengths is not None else [500.0, 550.0])
    timedelays = np.asarray(timedelays if timedelays is not None else [1.0, 2.0])
    return SimpleNamespace(
        file_path=file_path,
        number_maps=number_maps,
        wavelengths=wavelengths,
        timedelays=timedelays,
        wavelengths_length=len(wavelengths),
        timedelays_length=len(timedelays),
        scaling_yunit="ps",
        header="fake HIS",
    )


def _write_gzip_h5(file_path, compression_level=9):
    h5py = treatment_api_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")
    with h5py.File(file_path, "w") as h5_file:
        h5_file.create_dataset("timedelays", data=np.asarray([1.0, 2.0]))
        h5_file.create_dataset("wavelengths", data=np.asarray([500.0, 550.0]))
        h5_file.create_dataset(
            "raw_data",
            data=np.ones((2, 2, 2), dtype=float),
            compression="gzip",
            compression_opts=compression_level,
        )
        metadata = h5_file.create_group("metadata")
        metadata.attrs["compression"] = "gzip"
        metadata.attrs["compression_level"] = compression_level


class FakeHisOpener:
    def __init__(self, pairs):
        self._pairs = list(pairs)
        self.paths = {}

    def read_map(self, _file_path, map_index):
        flat_maps = [measurement for pair in self._pairs for measurement in pair]
        return flat_maps[map_index], ""

    def give_pair_maps(self, _file_path):
        return list(self._pairs)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(tmp_path))
    monkeypatch.setenv(
        "PYCONLYSE_TREATMENT_CACHE_DIR",
        str(tmp_path.parent / f"{tmp_path.name}_treatment_cache"),
    )
    monkeypatch.setenv("PYCONLYSE_TREATMENT_CACHE_LIMIT_BYTES", str(1024 * 1024))
    session_store.reset()

    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)

    with app.test_client() as test_client:
        yield test_client, tmp_path


def test_session_defaults_follow_allowed_root(client):
    test_client, tmp_path = client

    response = test_client.get("/api/treatment/session")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["session_id"]
    assert payload["allowed_root"] == str(tmp_path)
    assert payload["allowed_root_exists"] is True
    assert payload["cache_root"]
    assert payload["cache_limit_bytes"] == 1024 * 1024
    assert payload["session"]["folder_path"] == str(tmp_path)
    assert payload["session"]["save_folder"] == str(tmp_path)
    assert payload["exp_types"] == ["HIS", "HIS+NOISE", "ABS+BASE+NOISE"]
    assert payload["session"]["selected_data_type"] == "ABS+BASE"
    assert payload["session"]["required_data_types"] == ["ABS+BASE", "NOISE"]
    assert payload["session"]["missing_data_types"] == ["ABS+BASE", "NOISE"]
    assert payload["session"]["ready_for_calc"] is False


def test_set_folder_and_list_files(client):
    test_client, tmp_path = client
    session_payload = test_client.get("/api/treatment/session").get_json()
    h5_supported = ".h5" in session_payload["supported_suffixes"]
    data_dir = tmp_path / "run_001"
    data_dir.mkdir()
    (data_dir / "signal.h5").write_text("data", encoding="ascii")
    (data_dir / "notes.md").write_text("notes", encoding="ascii")
    (data_dir / "nested").mkdir()

    response = test_client.post(
        "/api/treatment/session/folder",
        json={"folder_path": str(data_dir)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["session"]["folder_path"] == str(data_dir)

    listing = test_client.get("/api/treatment/files", query_string={"folder": str(data_dir)})
    listing_payload = listing.get_json()

    assert listing.status_code == 200
    assert listing_payload["folders"] == [{"name": "nested", "path": str(data_dir / "nested")}]
    assert listing_payload["files"] == [
        {
            "name": "notes.md",
            "path": str(data_dir / "notes.md"),
            "size_bytes": 5,
            "suffix": ".md",
            "supported": False,
        },
        {
            "name": "signal.h5",
            "path": str(data_dir / "signal.h5"),
            "size_bytes": 4,
            "suffix": ".h5",
            "supported": h5_supported,
        },
    ]


def test_stitch_od_dat_endpoint_saves_joined_dat(client):
    test_client, tmp_path = client
    first = tmp_path / "blue.dat"
    second = tmp_path / "red.dat"
    _write_dat(first, [[1, 2], [10, 20]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[30, 40], [60, 70]], wavelengths=[435, 450], timedelays=[1, 2])

    response = test_client.post(
        "/api/treatment/stitch/od",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "output_folder": str(tmp_path),
            "output_file_name": "stitched.dat",
        },
    )
    payload = response.get_json()
    output = tmp_path / "stitched.dat"
    manifest = tmp_path / "stitched.manifest.json"

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["stitched"]["output_path"] == str(output)
    assert payload["stitched"]["manifest_path"] == str(manifest)
    assert payload["stitched"]["wavelengths"] == 4
    assert output.is_file()
    assert manifest.is_file()
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["operation"] == "vd2_od_stitch"
    assert manifest_payload["inputs"]["file_a"] == str(first)
    assert manifest_payload["inputs"]["file_b"] == str(second)
    assert manifest_payload["output"]["path"] == str(output)
    assert manifest_payload["stitch"]["axis_overlap_range"] == [435.0, 440.0]
    assert manifest_payload["coefficients"]["right_scale"] == 1.0
    saved = np.loadtxt(output)
    assert saved[0, 1:].tolist() == [1.0, 2.0]
    assert saved[1:, 0].tolist() == [420.0, 435.0, 440.0, 450.0]
    assert saved[2, 1:].tolist() == [18.875, 27.75]
    assert saved[3, 1:].tolist() == [25.0, 35.0]


def test_stitch_od_dat_endpoint_defaults_to_first_file_parent(client):
    test_client, tmp_path = client
    pair_folder = tmp_path / "pair"
    pair_folder.mkdir()
    first = pair_folder / "blue.dat"
    second = pair_folder / "red.dat"
    _write_dat(first, [[1, 2], [10, 20]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[30, 40], [60, 70]], wavelengths=[435, 450], timedelays=[1, 2])

    response = test_client.post(
        "/api/treatment/stitch/od",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "output_file_name": "stitched.dat",
        },
    )
    payload = response.get_json()
    output = pair_folder / "stitched.dat"

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["stitched"]["output_path"] == str(output)
    assert output.is_file()


def test_stitch_od_dat_endpoint_allows_default_stitch_root_output(client, monkeypatch):
    test_client, tmp_path = client
    allowed_root = tmp_path / "e" / "DATA_VD2"
    pair_folder = tmp_path / "f" / "DATA_VD2" / "pair"
    allowed_root.mkdir(parents=True)
    pair_folder.mkdir(parents=True)
    first = pair_folder / "blue.dat"
    second = pair_folder / "red.dat"
    _write_dat(first, [[1, 2], [10, 20]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[30, 40], [60, 70]], wavelengths=[435, 450], timedelays=[1, 2])
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(allowed_root))
    monkeypatch.setattr(
        treatment_api_module,
        "DEFAULT_STITCH_OD_ROOTS",
        (str(pair_folder.parent),),
    )

    response = test_client.post(
        "/api/treatment/stitch/od",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "output_folder": str(pair_folder),
            "output_file_name": "stitched.dat",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert (pair_folder / "stitched.dat").is_file()
    assert (pair_folder / "stitched.manifest.json").is_file()


def test_stitch_od_dat_endpoint_applies_right_delay_shift(client):
    test_client, tmp_path = client
    first = tmp_path / "blue.dat"
    second = tmp_path / "red.dat"
    _write_dat(first, [[1, 2], [10, 20]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[30, 40], [60, 70]], wavelengths=[435, 450], timedelays=[1, 2])

    response = test_client.post(
        "/api/treatment/stitch/od",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "output_folder": str(tmp_path),
            "output_file_name": "shifted.dat",
            "right_delay_shift_pixels": 1,
        },
    )
    output = tmp_path / "shifted.dat"
    manifest = tmp_path / "shifted.manifest.json"

    assert response.status_code == 200
    saved = np.loadtxt(output)
    assert saved[2, 1:].tolist() == [18.875, 22.75]
    assert saved[4, 1:].tolist() == [60.0, 60.0]
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["coefficients"]["right_delay_shift_pixels"] == 1


def test_stitch_od_dat_endpoint_uses_trusted_wavelength_ranges(client):
    test_client, tmp_path = client
    first = tmp_path / "blue.dat"
    second = tmp_path / "red.dat"
    _write_dat(
        first,
        [[1, 1], [10, 10], [20, 20], [999, 999]],
        wavelengths=[400, 420, 440, 460],
        timedelays=[1, 2],
    )
    _write_dat(
        second,
        [[999, 999], [40, 40], [100, 100], [999, 999]],
        wavelengths=[430, 440, 450, 470],
        timedelays=[1, 2],
    )

    response = test_client.post(
        "/api/treatment/stitch/od",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "output_folder": str(tmp_path),
            "output_file_name": "trusted.dat",
            "time_regions": [{
                "left_wavelength_start": 420,
                "left_wavelength_end": 440,
                "right_wavelength_start": 440,
                "right_wavelength_end": 450,
                "delay_start": 1,
                "delay_end": 2,
            }],
        },
    )
    output = tmp_path / "trusted.dat"

    assert response.status_code == 200
    saved = np.loadtxt(output, ndmin=2)
    assert saved[1:, 0].tolist() == [400.0, 420.0, 440.0, 450.0, 470.0]
    assert saved[1:, 1].tolist() == [1.0, 10.0, 30.0, 100.0, 999.0]


def test_stitch_od_preview_fits_right_map(client):
    test_client, tmp_path = client
    first = tmp_path / "blue.dat"
    second = tmp_path / "red.dat"
    _write_dat(first, [[10, 20], [30, 40]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[5, 10], [15, 20]], wavelengths=[420, 440], timedelays=[1, 2])

    response = test_client.post(
        "/api/treatment/stitch/od/preview",
        json={
            "file_a": str(first),
            "file_b": str(second),
            "fit_right": True,
            "time_regions": [{
                "left_wavelength_start": 420,
                "left_wavelength_end": 430,
                "right_wavelength_start": 420,
                "right_wavelength_end": 430,
                "delay_start": 1,
                "delay_end": 2,
            }],
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["stitch_preview"]["fit"]["right_scale"] == pytest.approx(2.0)
    assert payload["stitch_preview"]["fit"]["right_offset"] == pytest.approx(0.0)
    assert payload["stitch_preview"]["spectra"]


def test_stitch_od_preview_fit_ignores_existing_right_scale(client):
    test_client, tmp_path = client
    first = tmp_path / "blue.dat"
    second = tmp_path / "red.dat"
    _write_dat(first, [[10, 20], [30, 40]], wavelengths=[420, 440], timedelays=[1, 2])
    _write_dat(second, [[5, 10], [15, 20]], wavelengths=[420, 440], timedelays=[1, 2])
    request_payload = {
        "file_a": str(first),
        "file_b": str(second),
        "fit_right": True,
        "right_scale": 0.25,
        "right_offset": 123.0,
        "time_regions": [{
            "left_wavelength_start": 420,
            "left_wavelength_end": 430,
            "right_wavelength_start": 420,
            "right_wavelength_end": 430,
            "delay_start": 1,
            "delay_end": 2,
        }],
    }

    response = test_client.post("/api/treatment/stitch/od/preview", json=request_payload)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["stitch_preview"]["fit"]["right_scale"] == pytest.approx(2.0)
    assert payload["stitch_preview"]["coefficients"]["right_scale"] == pytest.approx(2.0)
    assert payload["stitch_preview"]["coefficients"]["right_offset"] == pytest.approx(0.0)


def test_update_treatment_root_from_session_endpoint(client):
    test_client, tmp_path = client
    new_root = tmp_path / "VD2"
    new_root.mkdir()

    response = test_client.post(
        "/api/treatment/session/root",
        json={"allowed_root": str(new_root)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["allowed_root"] == str(new_root)
    assert payload["allowed_root_exists"] is True
    assert payload["session"]["folder_path"] == str(new_root)
    assert payload["session"]["save_folder"] == str(new_root)
    assert payload["session"]["paths"] == {}


def test_smb_treatment_root_lists_network_files(client, monkeypatch):
    test_client, _tmp_path = client
    smb_root = r"\\Everest\e\Data\DATA_VD2"
    normalized_root = "smb://Everest/e/Data/DATA_VD2"

    monkeypatch.setattr(folder_api_module, "smb_isdir", lambda path: path == normalized_root)
    monkeypatch.setattr(treatment_api_module, "smb_isdir", lambda path: path == normalized_root)
    monkeypatch.setattr(
        treatment_api_module,
        "smb_listdir",
        lambda _folder: [
            {
                "name": "run_001",
                "path": f"{normalized_root}/run_001",
                "is_dir": True,
                "is_file": False,
            },
            {
                "name": "ABS001.his",
                "path": f"{normalized_root}/ABS001.his",
                "is_dir": False,
                "is_file": True,
            },
        ],
    )

    root_response = test_client.post(
        "/api/treatment/session/root",
        json={"allowed_root": smb_root},
    )
    root_payload = root_response.get_json()

    assert root_response.status_code == 200
    assert root_payload["allowed_root"] == normalized_root
    assert root_payload["allowed_root_exists"] is True
    assert root_payload["session"]["folder_path"] == normalized_root

    listing_response = test_client.get(
        "/api/treatment/files",
        query_string={"folder": normalized_root},
    )
    listing_payload = listing_response.get_json()

    assert listing_response.status_code == 200
    assert listing_payload["folders"] == [
        {"name": "run_001", "path": f"{normalized_root}/run_001"}
    ]
    assert listing_payload["files"] == [
        {
            "name": "ABS001.his",
            "path": f"{normalized_root}/ABS001.his",
            "size_bytes": 0,
            "suffix": ".his",
            "supported": True,
        }
    ]


def test_smb_local_map_lists_local_disk_with_smb_paths(client, monkeypatch):
    test_client, tmp_path = client
    local_root = tmp_path / "mapped_e"
    data_dir = local_root / "DATA_VD2"
    run_dir = data_dir / "run_001"
    run_dir.mkdir(parents=True)
    abs_file = data_dir / "ABS001.h5"
    abs_file.write_bytes(b"h5")
    smb_root = "smb://10.20.30.202/e"
    smb_data = f"{smb_root}/DATA_VD2"

    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", smb_root)
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", smb_root)
    monkeypatch.setenv("PYCONLYSE_SMB_LOCAL_MAP", f"{smb_root}/={local_root}")
    monkeypatch.setattr(
        treatment_api_module,
        "smb_listdir",
        lambda _path: (_ for _ in ()).throw(AssertionError("SMB listdir was called")),
    )
    monkeypatch.setattr(
        treatment_api_module,
        "smb_isdir",
        lambda _path: (_ for _ in ()).throw(AssertionError("SMB isdir was called")),
    )

    response = test_client.get("/api/treatment/files", query_string={"folder": smb_data})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["folders"] == [{"name": "run_001", "path": f"{smb_data}/run_001"}]
    assert payload["files"] == [
        {
            "name": "ABS001.h5",
            "path": f"{smb_data}/ABS001.h5",
            "size_bytes": 2,
            "suffix": ".h5",
            "supported": True,
        }
    ]


def test_cache_assignable_source_uses_smb_local_map_without_copy(tmp_path, monkeypatch):
    local_root = tmp_path / "mapped_e"
    source = local_root / "DATA_VD2" / "run_001" / "ABS001.h5"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"h5")
    smb_source = "smb://10.20.30.202/e/DATA_VD2/run_001/ABS001.h5"

    monkeypatch.setenv("PYCONLYSE_SMB_LOCAL_MAP", f"smb://10.20.30.202/e/={local_root}")
    monkeypatch.setattr(
        treatment_api_module,
        "smb_isfile",
        lambda _path: (_ for _ in ()).throw(AssertionError("SMB isfile was called")),
    )
    monkeypatch.setattr(
        treatment_api_module,
        "copy_smb_file_to_local",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("SMB copy was called")),
    )

    cached = treatment_api_module._cache_assignable_source(smb_source)

    assert cached["source_path"] == smb_source
    assert cached["cached_path"] == str(source)
    assert cached["copied"] is False
    assert cached["size_bytes"] == 2
    assert cached["cache"]["local_map"] is True


def test_file_summary_infers_time_scale_from_legacy_h5_path(client):
    h5py = treatment_api_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")

    test_client, tmp_path = client
    folder = tmp_path / "13113-water_600_1us-x0"
    folder.mkdir()
    file_path = folder / "ABS13113.h5"
    with h5py.File(file_path, "w") as h5_file:
        h5_file.create_dataset("timedelays", data=np.asarray([1.0, 2.0]))
        h5_file.create_dataset("wavelengths", data=np.asarray([421.0, 778.0]))
        h5_file.create_dataset("raw_data", data=np.ones((2, 2, 2), dtype=float))

    response = test_client.get(
        "/api/treatment/file-summary",
        query_string={"file_path": str(file_path)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["file_summary"]["number_maps"] == 2
    assert payload["file_summary"]["original_number_maps"] == 2
    assert payload["file_summary"]["time_scale"] == "us"
    assert payload["file_summary"]["timedelay_min"] == 1.0
    assert payload["file_summary"]["timedelay_max"] == 2.0
    assert payload["file_summary"]["wavelength_min"] == 421.0
    assert payload["file_summary"]["wavelength_max"] == 778.0


def test_update_treatment_root_rejects_paths_outside_root_base(client, tmp_path):
    test_client, _ = client
    outside_root = tmp_path.parent / "outside_vd2"
    outside_root.mkdir(exist_ok=True)

    response = test_client.post(
        "/api/treatment/session/root",
        json={"allowed_root": str(outside_root)},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert "Treatment root must be inside" in payload["error"]


def test_assign_file_and_update_config(client):
    test_client, tmp_path = client
    data_file = tmp_path / "abs_data.h5"
    data_file.write_text("content", encoding="ascii")

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    assign_payload = assign_response.get_json()

    assert assign_response.status_code == 200
    assert assign_payload["session"]["path_sources"]["ABS"] == str(data_file)
    assert assign_payload["session"]["paths"]["ABS"] == str(data_file)
    assert assign_payload["session"]["save_file_name"] == "abs_data.dat"

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={
            "exp_type": "ABS+BASE+NOISE",
            "selected_data_type": "NOISE",
            "calc_mode": "averaged",
            "first_map_with_electrons": False,
            "save_file_name": "result.dat",
        },
    )
    config_payload = config_response.get_json()

    assert config_response.status_code == 200
    assert config_payload["session"]["exp_type"] == "ABS+BASE+NOISE"
    assert config_payload["session"]["selected_data_type"] == "NOISE"
    assert config_payload["session"]["calc_mode"] == "averaged"
    assert config_payload["session"]["first_map_with_electrons"] is False
    assert config_payload["session"]["save_file_name"] == "result.dat"
    assert config_payload["session"]["required_data_types"] == ["ABS", "BASE", "NOISE"]
    assert config_payload["session"]["missing_data_types"] == ["BASE", "NOISE"]
    assert config_payload["session"]["ready_for_calc"] is False


def test_cache_and_assign_copies_file_to_server_cache(client):
    test_client, tmp_path = client
    data_file = tmp_path / "ABS001.dat"
    _write_dat(data_file, np.array([[1.0, 2.0], [3.0, 4.0]]))

    response = test_client.post(
        "/api/treatment/session/cache-path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    payload = response.get_json()
    cached_path = Path(payload["cached_file"]["cached_path"])

    assert response.status_code == 200
    assert cached_path.is_file()
    assert cached_path != data_file
    assert payload["session"]["paths"]["ABS"] == str(cached_path)
    assert payload["session"]["path_sources"]["ABS"] == str(data_file)
    assert payload["cached_file"]["source_path"] == str(data_file)
    assert payload["cached_file"]["cache"]["size_bytes"] >= data_file.stat().st_size

    preview_response = test_client.get(
        "/api/treatment/preview",
        query_string={"data_type": "ABS", "map_index": 0},
    )
    preview_payload = preview_response.get_json()

    assert preview_response.status_code == 200
    assert preview_payload["preview"]["sample"] == [[1.0, 2.0], [3.0, 4.0]]


def test_cache_and_assign_copies_smb_file_to_server_cache(client, monkeypatch):
    test_client, _tmp_path = client
    smb_root = "smb://Everest/e/Data/DATA_VD2"
    smb_file = f"{smb_root}/ABS001.his"

    monkeypatch.setattr(folder_api_module, "smb_isdir", lambda path: path == smb_root)
    monkeypatch.setattr(treatment_api_module, "smb_isdir", lambda path: path == smb_root)
    monkeypatch.setattr(treatment_api_module, "smb_isfile", lambda path: path == smb_file)

    def fake_copy_smb_file_to_local(_source_path, target_path):
        Path(target_path).write_bytes(b"fake his")
        return len(b"fake his")

    monkeypatch.setattr(
        treatment_api_module,
        "copy_smb_file_to_local",
        fake_copy_smb_file_to_local,
    )

    root_response = test_client.post(
        "/api/treatment/session/root",
        json={"allowed_root": r"\\Everest\e\Data\DATA_VD2"},
    )
    assert root_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/cache-path",
        json={"data_type": "ABS+BASE+NOISE", "file_path": smb_file},
    )
    payload = response.get_json()
    cached_path = Path(payload["cached_file"]["cached_path"])

    assert response.status_code == 200
    assert cached_path.is_file()
    assert cached_path.read_bytes() == b"fake his"
    assert payload["cached_file"]["source_path"] == smb_file
    assert payload["session"]["paths"]["ABS+BASE+NOISE"] == str(cached_path)
    assert payload["session"]["path_sources"]["ABS+BASE+NOISE"] == smb_file


def test_compress_and_assign_converts_his_to_h5_and_deletes_source(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.his"
    source_file.write_bytes(b"fake his payload")
    output_file = tmp_path / "ABS12886.h5"

    def fake_convert(source_path, output_path, progress_callback=None):
        Path(output_path).write_bytes(b"compressed h5 payload")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 10,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-path",
        json={"data_type": "ABS", "file_path": str(source_file)},
    )
    payload = response.get_json()
    cached_path = Path(payload["cached_file"]["cached_path"])

    assert response.status_code == 200
    assert not source_file.exists()
    assert output_file.is_file()
    assert cached_path.read_bytes() == b"compressed h5 payload"
    assert payload["conversion"]["converted"] is True
    assert payload["conversion"]["deleted_source"] is True
    assert payload["conversion"]["source_size_bytes"] == len(b"fake his payload")
    assert payload["conversion"]["output_size_bytes"] == len(b"compressed h5 payload")
    assert payload["session"]["paths"]["ABS"] == str(cached_path)
    assert payload["session"]["path_sources"]["ABS"] == str(output_file)


def test_compress_and_assign_overwrites_h5_without_deleting_source(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) == Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        Path(output_path).write_bytes(b"recompressed h5 payload")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 10,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-path",
        json={"data_type": "ABS", "file_path": str(source_file)},
    )
    payload = response.get_json()
    cached_path = Path(payload["cached_file"]["cached_path"])

    assert response.status_code == 200
    assert source_file.read_bytes() == b"recompressed h5 payload"
    assert cached_path.read_bytes() == b"recompressed h5 payload"
    assert payload["conversion"]["converted"] is True
    assert payload["conversion"]["overwritten"] is True
    assert payload["conversion"]["deleted_source"] is False
    assert payload["conversion"]["source_size_bytes"] == len(b"old h5 payload")
    assert payload["conversion"]["output_size_bytes"] == len(b"recompressed h5 payload")
    assert payload["session"]["path_sources"]["ABS"] == str(source_file)


def test_compress_file_endpoint_does_not_assign_input(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) == Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        Path(output_path).write_bytes(b"recompressed h5 payload")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 10,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-file",
        json={"file_path": str(source_file)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert source_file.read_bytes() == b"recompressed h5 payload"
    assert payload["conversion"]["overwritten"] is True
    assert payload["session"]["paths"] == {}
    assert payload["session"]["path_sources"] == {}


def test_compress_file_start_reports_job_progress(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) == Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        Path(output_path).write_bytes(b"recompressed h5 payload")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 10,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-file/start",
        json={"file_path": str(source_file)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    job_id = payload["compression_job"]["job_id"]
    status_payload = None
    for _attempt in range(20):
        status_response = test_client.get(f"/api/treatment/session/compress-file/status/{job_id}")
        status_payload = status_response.get_json()
        if status_payload["compression_job"]["status"] == "complete":
            break
        time.sleep(0.05)

    job = status_payload["compression_job"]
    assert job["status"] == "complete"
    assert job["conversion"]["overwritten"] is True
    assert job["conversion"]["output_size_bytes"] == len(b"recompressed h5 payload")
    assert job["payload"]["conversion"]["output_path"] == str(source_file)


def test_compress_file_skips_existing_gzip_h5(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    _write_gzip_h5(source_file, compression_level=9)
    original_bytes = source_file.read_bytes()

    def fail_convert(*_args, **_kwargs):
        raise AssertionError("already compressed H5 should not be rewritten")

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fail_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-file",
        json={"file_path": str(source_file)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert source_file.read_bytes() == original_bytes
    assert payload["conversion"]["converted"] is False
    assert payload["conversion"]["overwritten"] is False
    assert payload["conversion"]["reused_compressed"] is True
    assert payload["conversion"]["compression"] == "gzip"
    assert payload["conversion"]["compression_level"] == 9


def test_folder_set_convert_clean_deletes_his_and_assigns_cleaned_h5(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "20260127"
    folder.mkdir()
    abs_his = folder / "ABS12886.his"
    base_his = folder / "BASE12886.his"
    abs_his.write_bytes(b"abs his")
    base_his.write_bytes(b"base his")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    def fake_convert(source_path, output_path, progress_callback=None):
        Path(output_path).write_bytes(b"converted h5")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 10,
        }

    cleaned_types = []

    def fake_save(session_id, session_state, angle_threshold, surface_threshold, output_file_name=""):
        data_type = session_state["active_data_type"]
        source_path = Path(session_state["path_sources"][data_type])
        source_path.write_bytes(f"cleaned {data_type}".encode("ascii"))
        cleaned_types.append(data_type)
        return {
            "file_path": session_state["paths"][data_type],
            "source_file_path": str(source_path),
            "output_path": str(source_path),
            "original_measurements": 10,
            "cleaned_measurements": 8,
            "removed_measurements": 2,
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )
    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_sam_cleaned_h5",
        fake_save,
    )

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={
            "folder_path": str(folder),
            "convert": True,
            "clean": True,
            "angle_threshold": 2.5,
            "surface_threshold": 9.0,
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert not abs_his.exists()
    assert not base_his.exists()
    assert (folder / "ABS12886.h5").read_bytes() == b"cleaned ABS"
    assert (folder / "BASE12886.h5").read_bytes() == b"cleaned BASE"
    assert sorted(cleaned_types) == ["ABS", "BASE"]
    assert payload["folder_set"]["convert"] is True
    assert payload["folder_set"]["clean"] is True
    assert payload["folder_set"]["conversions"]["ABS"]["deleted_source"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["deleted_source"] is True
    assert payload["folder_set"]["conversions"]["ABS"]["source_size_bytes"] == len(b"abs his")
    assert payload["folder_set"]["conversions"]["ABS"]["output_size_bytes"] == len(b"converted h5")
    assert payload["folder_set"]["conversions"]["ABS"]["space_change_bytes"] == (
        len(b"converted h5") - len(b"abs his")
    )
    assert payload["folder_set"]["cleaned"]["ABS"]["output_path"] == str(folder / "ABS12886.h5")
    assert payload["session"]["path_sources"]["ABS"] == str(folder / "ABS12886.h5")
    assert payload["session"]["path_sources"]["BASE"] == str(folder / "BASE12886.h5")


def test_folder_set_his_noise_allows_abs_base_without_folder_noise(client):
    test_client, tmp_path = client
    folder = tmp_path / "sample_without_noise"
    folder.mkdir()
    abs_base_path = folder / "ABS010.his"
    previous_noise_path = tmp_path / "previous_NOISE.his"
    abs_base_path.write_bytes(b"abs base his")
    previous_noise_path.write_bytes(b"previous noise")

    noise_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "NOISE", "file_path": str(previous_noise_path)},
    )
    assert noise_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["folder_set"]["assigned"] == {
        "ABS+BASE": payload["session"]["paths"]["ABS+BASE"]
    }
    assert payload["session"]["path_sources"]["ABS+BASE"] == str(abs_base_path)
    assert payload["session"]["path_sources"]["NOISE"] == str(previous_noise_path)
    assert payload["session"]["ready_for_calc"] is True


def test_folder_set_abs_base_noise_requires_abs_and_base_not_noise(client):
    test_client, tmp_path = client
    folder = tmp_path / "missing_base"
    folder.mkdir()
    (folder / "ABS001.his").write_bytes(b"abs his")
    (folder / "BRUIT001.his").write_bytes(b"noise his")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder)},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert "missing BASE" in payload["error"]
    assert "found ABS, NOISE" in payload["error"]


def test_folder_set_convert_runs_conversions_in_parallel(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "parallel"
    folder.mkdir()
    source_files = [
        folder / "ABS001.his",
        folder / "BASE001.his",
        folder / "BRUIT001.his",
    ]
    for source_file in source_files:
        source_file.write_bytes(b"his")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    lock = Lock()
    active = {"current": 0, "max": 0}

    def fake_convert(source_path, progress_callback=None):
        source = Path(source_path)
        output = source.with_suffix(".h5")
        if progress_callback:
            progress_callback("download", 1, 3, "Reading source file")
        with lock:
            active["current"] += 1
            active["max"] = max(active["max"], active["current"])
        try:
            if progress_callback:
                progress_callback("convert", 1, 2, "Compressing map 1/2")
            time.sleep(0.1)
            output.write_bytes(f"h5 {source.stem}".encode("ascii"))
            source.unlink()
            if progress_callback:
                progress_callback("upload", 3, 3, "Writing compressed H5")
            return {
                "source_path": str(source),
                "output_path": str(output),
                "converted": True,
                "deleted_source": True,
                "source_size_bytes": len(b"his"),
                "output_size_bytes": output.stat().st_size,
                "space_change_bytes": output.stat().st_size - len(b"his"),
                "space_change_percent": 0.0,
            }
        finally:
            with lock:
                active["current"] -= 1

    monkeypatch.setattr(treatment_api_module, "_convert_source_to_h5", fake_convert)

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder), "convert": True},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert active["max"] > 1
    assert sorted(payload["folder_set"]["conversions"]) == ["ABS", "BASE", "NOISE"]
    assert payload["session"]["path_sources"]["ABS"] == str(folder / "ABS001.h5")
    assert payload["session"]["path_sources"]["BASE"] == str(folder / "BASE001.h5")
    assert payload["session"]["path_sources"]["NOISE"] == str(folder / "BRUIT001.h5")


def test_smb_folder_convert_stages_io_and_converts_locally_in_parallel(monkeypatch, tmp_path):
    selected_paths = {
        "ABS": "smb://10.20.30.202/e/DATA_VD2/run/ABS001.his",
        "BASE": "smb://10.20.30.202/e/DATA_VD2/run/BASE001.his",
        "NOISE": "smb://10.20.30.202/e/DATA_VD2/run/BRUIT001.his",
    }
    events = []
    active = {"current": 0, "max": 0}
    lock = Lock()

    monkeypatch.setattr(treatment_api_module, "_smb_size_bytes", lambda _path: 3)
    monkeypatch.setattr(treatment_api_module, "smb_isfile", lambda path: path.endswith(".h5"))

    def fake_download(source_path, local_path, progress_callback=None):
        with lock:
            events.append(("download", Path(source_path).name))
        Path(local_path).write_bytes(b"his")
        if progress_callback:
            progress_callback(3)
        return 3

    def fake_convert(source_path, output_path, progress_callback=None):
        with lock:
            active["current"] += 1
            active["max"] = max(active["max"], active["current"])
            events.append(("convert-start", Path(source_path).name))
        try:
            time.sleep(0.05)
            Path(output_path).write_bytes(f"h5 {Path(source_path).stem}".encode("ascii"))
            if progress_callback:
                progress_callback(1, 1)
            return {
                "source_path": str(source_path),
                "output_path": str(output_path),
                "original_measurements": 1,
                "compression": "gzip",
                "compression_level": 4,
            }
        finally:
            with lock:
                active["current"] -= 1
                events.append(("convert-end", Path(source_path).name))

    def fake_upload(local_path, smb_path, progress_callback=None):
        with lock:
            events.append(("upload", Path(smb_path).name))
        if progress_callback:
            progress_callback(Path(local_path).stat().st_size)
        return Path(local_path).stat().st_size

    def fake_remove(path):
        with lock:
            events.append(("delete", Path(path).name))

    monkeypatch.setattr(treatment_api_module, "copy_smb_file_to_local", fake_download)
    monkeypatch.setattr(treatment_api_module.treatment_service, "convert_file_to_h5", fake_convert)
    monkeypatch.setattr(treatment_api_module, "copy_local_file_to_smb_atomic", fake_upload)
    monkeypatch.setattr(treatment_api_module, "smb_remove", fake_remove)

    conversions = treatment_api_module._convert_smb_sources_to_h5_pipeline(selected_paths)
    event_names = [name for name, _detail in events]
    first_convert = event_names.index("convert-start")
    first_upload = event_names.index("upload")

    assert event_names[:3] == ["download", "download", "download"]
    assert all(name.startswith("convert") for name in event_names[first_convert:first_upload])
    assert active["max"] > 1
    assert sorted(conversions) == ["ABS", "BASE", "NOISE"]
    assert conversions["ABS"]["output_path"].endswith("/ABS001.h5")
    assert conversions["BASE"]["output_path"].endswith("/BASE001.h5")
    assert conversions["NOISE"]["output_path"].endswith("/BRUIT001.h5")


def test_folder_set_convert_replaces_existing_gzip_h5_from_his(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "already_converted"
    folder.mkdir()
    abs_his = folder / "ABS001.his"
    base_his = folder / "BASE001.his"
    abs_h5 = folder / "ABS001.h5"
    base_h5 = folder / "BASE001.h5"
    abs_his.write_bytes(b"abs his")
    base_his.write_bytes(b"base his")
    _write_gzip_h5(abs_h5, compression_level=9)
    _write_gzip_h5(base_h5, compression_level=4)
    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    def fake_convert(source_path, output_path, progress_callback=None):
        if progress_callback:
            progress_callback(1, 1)
        source = Path(source_path)
        Path(output_path).write_bytes(f"converted {source.stem}".encode("ascii"))
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 1,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder), "convert": True},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert not abs_his.exists()
    assert not base_his.exists()
    assert abs_h5.read_bytes() == b"converted ABS001"
    assert base_h5.read_bytes() == b"converted BASE001"
    assert payload["folder_set"]["conversions"]["ABS"]["converted"] is True
    assert payload["folder_set"]["conversions"]["ABS"]["overwritten"] is True
    assert payload["folder_set"]["conversions"]["ABS"]["deleted_source"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["converted"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["overwritten"] is True
    assert payload["session"]["path_sources"]["ABS"] == str(abs_h5)
    assert payload["session"]["path_sources"]["BASE"] == str(base_h5)


def test_folder_set_convert_mixed_h5_and_his_converts_remaining_his(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "mixed_h5_his"
    folder.mkdir()
    abs_h5 = folder / "ABS001.h5"
    base_his = folder / "BASE001.his"
    base_h5 = folder / "BASE001.h5"
    _write_gzip_h5(abs_h5, compression_level=4)
    base_his.write_bytes(b"base his")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    def fake_convert(source_path, output_path, progress_callback=None):
        if progress_callback:
            progress_callback(1, 1)
        Path(output_path).write_bytes(b"converted base h5")
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 1,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder), "convert": True},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert not base_his.exists()
    assert base_h5.read_bytes() == b"converted base h5"
    assert payload["folder_set"]["conversions"]["ABS"]["reused_compressed"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["converted"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["deleted_source"] is True
    assert payload["session"]["path_sources"]["ABS"] == str(abs_h5)
    assert payload["session"]["path_sources"]["BASE"] == str(base_h5)


def test_folder_set_his_noise_mode_detects_separate_abs_base_folder(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "13116-0.1 M NH3_CO_600_1us-x0"
    folder.mkdir()
    abs_h5 = folder / "ABS13116.h5"
    base_h5 = folder / "BASE13116.h5"
    base_his = folder / "BASE13116.his"
    _write_gzip_h5(abs_h5, compression_level=4)
    _write_gzip_h5(base_h5, compression_level=4)
    base_his.write_bytes(b"new base his")

    def fake_convert(source_path, output_path, progress_callback=None):
        if progress_callback:
            progress_callback(1, 1)
        source = Path(source_path)
        Path(output_path).write_bytes(f"converted {source.stem}".encode("ascii"))
        return {
            "source_path": str(source_path),
            "output_path": str(output_path),
            "original_measurements": 1,
            "compression": "gzip",
            "compression_level": 4,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder), "convert": True},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert not base_his.exists()
    assert base_h5.read_bytes() == b"converted BASE13116"
    assert payload["session"]["exp_type"] == "ABS+BASE+NOISE"
    assert payload["folder_set"]["conversions"]["ABS"]["reused_compressed"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["converted"] is True
    assert payload["folder_set"]["conversions"]["BASE"]["overwritten"] is True
    assert payload["session"]["path_sources"]["ABS"] == str(abs_h5)
    assert payload["session"]["path_sources"]["BASE"] == str(base_h5)


def test_folder_set_start_reports_job_progress(client, monkeypatch):
    test_client, tmp_path = client
    folder = tmp_path / "async_parallel"
    folder.mkdir()
    abs_his = folder / "ABS001.his"
    base_his = folder / "BASE001.his"
    abs_his.write_bytes(b"abs his")
    base_his.write_bytes(b"base his")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    def fake_convert(source_path, progress_callback=None):
        source = Path(source_path)
        output = source.with_suffix(".h5")
        if progress_callback:
            progress_callback("download", 1, 3, "Reading source file")
        time.sleep(0.1)
        if progress_callback:
            progress_callback("convert", 1, 2, "Compressing map 1/2")
        output.write_bytes(f"h5 {source.stem}".encode("ascii"))
        source.unlink()
        if progress_callback:
            progress_callback("upload", 3, 3, "Writing compressed H5")
        return {
            "source_path": str(source),
            "output_path": str(output),
            "converted": True,
            "deleted_source": True,
            "source_size_bytes": len(b"abs his"),
            "output_size_bytes": output.stat().st_size,
            "space_change_bytes": output.stat().st_size - len(b"abs his"),
            "space_change_percent": 0.0,
        }

    monkeypatch.setattr(treatment_api_module, "_convert_source_to_h5", fake_convert)

    response = test_client.post(
        "/api/treatment/session/folder-set/start",
        json={"folder_path": str(folder), "convert": True},
    )
    payload = response.get_json()

    assert response.status_code == 200
    job_id = payload["folder_set_job"]["job_id"]
    assert payload["folder_set_job"]["status"] == "running"

    status_payload = None
    observed_progress = False
    observed_inner_phase = False
    for _attempt in range(20):
        status_response = test_client.get(f"/api/treatment/session/folder-set/status/{job_id}")
        status_payload = status_response.get_json()
        job = status_payload["folder_set_job"]
        observed_progress = observed_progress or bool(job.get("files"))
        observed_inner_phase = observed_inner_phase or any(
            item.get("phase") in {"download", "convert", "upload"}
            and item.get("total", 0) > 0
            for item in job.get("files", {}).values()
        )
        if job["status"] == "complete":
            break
        time.sleep(0.05)

    job = status_payload["folder_set_job"]
    assert observed_progress is True
    assert observed_inner_phase is True
    assert job["status"] == "complete"
    assert job["payload"]["folder_set"]["conversions"]["ABS"]["deleted_source"] is True
    assert job["payload"]["session"]["path_sources"]["ABS"] == str(folder / "ABS001.h5")
    assert job["payload"]["session"]["path_sources"]["BASE"] == str(folder / "BASE001.h5")


def test_auto_assign_smb_folder_caches_abs_base_bruit_his(client, monkeypatch):
    test_client, _tmp_path = client
    smb_root = "smb://Everest/e/Data/DATA_VD2"
    smb_folder = f"{smb_root}/20260127/water"
    abs_file = f"{smb_folder}/ABS12886.his"
    base_h5 = f"{smb_folder}/BASE12886.h5"
    base_file = f"{smb_folder}/BASE12886.his"
    bruit_file = f"{smb_folder}/BRUIT12886.his"

    monkeypatch.setattr(
        folder_api_module,
        "smb_isdir",
        lambda path: path in {smb_root, smb_folder},
    )
    monkeypatch.setattr(
        treatment_api_module,
        "smb_isdir",
        lambda path: path in {smb_root, smb_folder},
    )
    monkeypatch.setattr(
        treatment_api_module,
        "smb_isfile",
        lambda path: path in {abs_file, base_h5, base_file, bruit_file},
    )
    monkeypatch.setattr(
        treatment_api_module,
        "smb_listdir",
        lambda _folder: [
            {
                "name": "ABS12886.his",
                "path": abs_file,
                "is_dir": False,
                "is_file": True,
            },
            {
                "name": "BASE12886.h5",
                "path": base_h5,
                "is_dir": False,
                "is_file": True,
            },
            {
                "name": "BASE12886.his",
                "path": base_file,
                "is_dir": False,
                "is_file": True,
            },
            {
                "name": "BRUIT12886.his",
                "path": bruit_file,
                "is_dir": False,
                "is_file": True,
            },
        ],
    )

    def fake_copy_smb_file_to_local(source_path, target_path):
        Path(target_path).write_bytes(Path(source_path).name.encode("ascii"))
        return Path(target_path).stat().st_size

    monkeypatch.setattr(
        treatment_api_module,
        "copy_smb_file_to_local",
        fake_copy_smb_file_to_local,
    )

    root_response = test_client.post(
        "/api/treatment/session/root",
        json={"allowed_root": smb_root},
    )
    assert root_response.status_code == 200

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/auto-assign",
        json={"folder_path": smb_folder},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["auto_assign_missing"] == []
    assert payload["session"]["ready_for_calc"] is True
    assert payload["session"]["save_folder"] == f"{smb_root}/20260127"
    assert payload["session"]["save_file_name"] == "water.dat"
    assert payload["auto_assigned_cached_files"]["ABS"]["source_path"] == abs_file
    assert payload["auto_assigned_cached_files"]["BASE"]["source_path"] == base_file
    assert payload["auto_assigned_cached_files"]["NOISE"]["source_path"] == bruit_file

    assigned = payload["auto_assigned"]
    assert Path(assigned["ABS"]).read_bytes() == b"ABS12886.his"
    assert Path(assigned["BASE"]).read_bytes() == b"BASE12886.his"
    assert Path(assigned["NOISE"]).read_bytes() == b"BRUIT12886.his"


def test_his_cache_preview_calculate_and_save_flow(client, monkeypatch):
    test_client, tmp_path = client
    his_path = tmp_path / "ABS001.his"
    his_path.write_text("fake his payload", encoding="ascii")
    pair_opener = FakeHisOpener(
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

    def fake_get_opener_and_info(path):
        info = _critical_info(path, 4)
        pair_opener.paths[path] = info
        return pair_opener, info

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "_get_opener_and_info",
        fake_get_opener_and_info,
    )

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={
            "exp_type": "HIS",
            "selected_data_type": "ABS+BASE+NOISE",
            "calc_mode": "averaged",
        },
    )
    assert config_response.status_code == 200

    assign_response = test_client.post(
        "/api/treatment/session/cache-path",
        json={"data_type": "ABS+BASE+NOISE", "file_path": str(his_path)},
    )
    assign_payload = assign_response.get_json()

    assert assign_response.status_code == 200
    assert assign_payload["session"]["ready_for_calc"] is True
    assert Path(assign_payload["cached_file"]["cached_path"]).is_file()

    preview_response = test_client.get(
        "/api/treatment/preview",
        query_string={"data_type": "ABS+BASE+NOISE", "map_index": 0},
    )
    preview_payload = preview_response.get_json()

    assert preview_response.status_code == 200
    assert preview_payload["preview"]["data_shape"] == [2, 2]
    assert preview_payload["preview"]["sample"] == [[2.0, 2.0], [2.0, 2.0]]

    calc_response = test_client.post("/api/treatment/calc-abs")
    calc_payload = calc_response.get_json()
    expected = np.log10(np.full((2, 2), 2.0, dtype=float))

    assert calc_response.status_code == 200
    assert calc_payload["session"]["result_ready"] is True
    assert calc_payload["session"]["result_shape"] == [2, 2]
    assert np.allclose(np.asarray(calc_payload["result"]["sample"]), expected)

    save_response = test_client.post("/api/treatment/save")
    save_payload = save_response.get_json()

    assert save_response.status_code == 200
    assert Path(save_payload["saved"]["save_path"]).is_file()


def test_auto_assign_abs_base_noise_files_from_current_folder(client):
    test_client, tmp_path = client
    data_dir = tmp_path / "run_auto"
    data_dir.mkdir()
    abs_path = data_dir / "ABS001.dat"
    base_path = data_dir / "BASE001.dat"
    noise_path = data_dir / "NOISE001.dat"
    _write_dat(abs_path, np.array([[1.0, 2.0], [3.0, 4.0]]))
    _write_dat(base_path, np.array([[2.0, 3.0], [4.0, 5.0]]))
    _write_dat(noise_path, np.array([[0.1, 0.2], [0.3, 0.4]]))
    (data_dir / "notes.txt").write_text("ignored", encoding="ascii")

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/auto-assign",
        json={"folder_path": str(data_dir)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["auto_assigned"] == {
        "ABS": str(abs_path),
        "BASE": str(base_path),
        "NOISE": str(noise_path),
    }
    assert payload["auto_assign_missing"] == []
    assert payload["session"]["ready_for_calc"] is True


def test_folder_set_auto_calculates_od_when_inputs_ready(client):
    test_client, tmp_path = client
    data_dir = tmp_path / "folder_auto_calc"
    data_dir.mkdir()
    abs_data = np.array([[1.0, 2.0], [3.0, 4.0]])
    base_data = np.array([[2.0, 3.0], [4.0, 5.0]])
    noise_data = np.array([[0.1, 0.2], [0.3, 0.4]])
    _write_dat(data_dir / "ABS001.dat", abs_data)
    _write_dat(data_dir / "BASE001.dat", base_data)
    _write_dat(data_dir / "BRUIT001.dat", noise_data)

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE"},
    )
    assert config_response.status_code == 200

    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(data_dir)},
    )
    payload = response.get_json()
    expected = np.log10((base_data - noise_data) / (abs_data - noise_data))

    assert response.status_code == 200
    assert payload["folder_set"]["auto_calculated"] is True
    assert payload["session"]["active_data_type"] == "OD"
    assert payload["session"]["result_ready"] is True
    assert np.allclose(np.asarray(payload["result"]["sample"]), expected)


def test_auto_assign_his_noise_uses_abs_base_plus_noise(client):
    test_client, tmp_path = client
    data_dir = tmp_path / "run_his_noise"
    data_dir.mkdir()
    abs_base_path = data_dir / "ABS010.his"
    noise_path = data_dir / "NOISE010.img"
    abs_base_path.write_text("placeholder", encoding="ascii")
    noise_path.write_text("placeholder", encoding="ascii")

    response = test_client.post(
        "/api/treatment/session/auto-assign",
        json={"folder_path": str(data_dir)},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["session"]["exp_type"] == "HIS+NOISE"
    assert payload["auto_assigned"] == {
        "ABS+BASE": str(abs_base_path),
        "NOISE": str(noise_path),
    }
    assert payload["auto_assign_missing"] == []
    assert payload["session"]["ready_for_calc"] is True


def test_rejects_selected_data_type_incompatible_with_exp_type(client):
    test_client, _ = client

    response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "HIS", "selected_data_type": "ABS"},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert "is not valid for exp_type" in payload["error"]


def test_rejects_paths_outside_allowed_root(client, tmp_path):
    test_client, _ = client
    outside_dir = tmp_path.parent / "outside"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "bad.h5"
    outside_file.write_text("bad", encoding="ascii")

    response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(outside_file)},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert "outside the allowed treatment root" in payload["error"]


def test_preview_and_calc_abs_work_with_server_local_files(client):
    test_client, tmp_path = client
    abs_data = np.array([[3.0, 4.0], [5.0, 6.0]])
    base_data = np.array([[5.0, 7.0], [9.0, 11.0]])
    noise_data = np.array([[1.0, 1.0], [1.0, 1.0]])

    abs_path = tmp_path / "abs.dat"
    base_path = tmp_path / "base.dat"
    noise_path = tmp_path / "noise.dat"
    _write_dat(abs_path, abs_data)
    _write_dat(base_path, base_data)
    _write_dat(noise_path, noise_data)

    for data_type, file_path in (
        ("ABS", abs_path),
        ("BASE", base_path),
        ("NOISE", noise_path),
    ):
        response = test_client.post(
            "/api/treatment/session/path",
            json={"data_type": data_type, "file_path": str(file_path)},
        )
        assert response.status_code == 200

    preview_response = test_client.get(
        "/api/treatment/preview",
        query_string={"data_type": "ABS", "map_index": 0},
    )
    preview_payload = preview_response.get_json()

    assert preview_response.status_code == 200
    assert preview_payload["preview"]["file_info"]["suffix"] == ".dat"
    assert preview_payload["preview"]["data_shape"] == [2, 2]
    assert preview_payload["preview"]["sample"] == [[3.0, 4.0], [5.0, 6.0]]

    config_response = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE", "save_file_name": "od_result.dat"},
    )
    assert config_response.status_code == 200

    noise_response = test_client.post("/api/treatment/average-noise")
    noise_payload = noise_response.get_json()

    assert noise_response.status_code == 200
    assert noise_payload["noise"]["shape"] == [2, 2]
    assert noise_payload["session"]["noise_ready"] is True

    calc_response = test_client.post("/api/treatment/calc-abs")
    calc_payload = calc_response.get_json()

    expected = np.log10((base_data - noise_data) / (abs_data - noise_data))

    assert calc_response.status_code == 200
    assert calc_payload["session"]["result_ready"] is True
    assert calc_payload["session"]["result_shape"] == [2, 2]
    assert np.allclose(np.array(calc_payload["result"]["sample"]), expected)

    rename_response = test_client.post(
        "/api/treatment/session/config",
        json={"save_file_name": "od_result_b.dat", "calc_mode": "averaged"},
    )
    rename_payload = rename_response.get_json()

    assert rename_response.status_code == 200
    assert rename_payload["session"]["save_file_name"] == "od_result_b.dat"
    assert rename_payload["session"]["result_ready"] is True

    save_response = test_client.post("/api/treatment/save")
    save_payload = save_response.get_json()
    save_path = Path(save_payload["saved"]["save_path"])

    assert save_response.status_code == 200
    assert save_path.name == "od_result_b.dat"
    assert save_path.is_file()
    saved = np.loadtxt(save_path)
    assert saved.shape == (3, 3)


def test_selection_view_uses_active_file_and_cursor_ranges(client):
    test_client, tmp_path = client
    abs_data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    abs_path = tmp_path / "selection_abs.dat"
    _write_dat(
        abs_path,
        abs_data,
        wavelengths=[500, 550, 600],
        timedelays=[1, 2, 3],
    )

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(abs_path)},
    )
    assign_payload = assign_response.get_json()

    assert assign_response.status_code == 200
    assert assign_payload["session"]["active_data_type"] == "ABS"

    selection_response = test_client.post(
        "/api/treatment/session/selection",
        json={
            "active_data_type": "ABS",
            "map_index": 0,
            "selection": {"x1": 1, "x2": 2, "y1": 0, "y2": 1},
        },
    )
    selection_payload = selection_response.get_json()

    assert selection_response.status_code == 200
    assert selection_payload["session"]["selection"] == {"x1": 1, "x2": 2, "y1": 0, "y2": 1}

    view_response = test_client.get("/api/treatment/selection")
    view_payload = view_response.get_json()

    assert view_response.status_code == 200
    assert view_payload["selection"]["active_data_type"] == "ABS"
    assert view_payload["selection"]["map_index"] == 0
    assert view_payload["selection"]["kinetics"]["y"] == [4.0, 5.0, 6.0]
    assert view_payload["selection"]["spectrum"]["y"] == [1.0, 4.0, 7.0]


def test_assigning_new_file_preserves_selection_cursors(client):
    test_client, tmp_path = client
    first_path = tmp_path / "selection_first.dat"
    second_path = tmp_path / "selection_second.dat"
    _write_dat(
        first_path,
        np.ones((3, 3)),
        wavelengths=[500, 550, 600],
        timedelays=[1, 2, 3],
    )
    _write_dat(
        second_path,
        np.ones((3, 3)) * 2,
        wavelengths=[500, 550, 600],
        timedelays=[1, 2, 3],
    )

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(first_path)},
    )
    assert assign_response.status_code == 200

    selection_response = test_client.post(
        "/api/treatment/session/selection",
        json={
            "active_data_type": "ABS",
            "selection": {"x1": 1, "x2": 2, "y1": 0, "y2": 1},
        },
    )
    assert selection_response.status_code == 200

    second_assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(second_path)},
    )
    second_payload = second_assign_response.get_json()

    assert second_assign_response.status_code == 200
    assert second_payload["session"]["selection"] == {"x1": 1, "x2": 2, "y1": 0, "y2": 1}


def test_selection_export_writes_averaged_kinetics_file(client):
    test_client, tmp_path = client
    abs_data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    abs_path = tmp_path / "export_abs.dat"
    _write_dat(
        abs_path,
        abs_data,
        wavelengths=[500, 550, 600],
        timedelays=[1, 2, 3],
    )

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(abs_path)},
    )
    assert assign_response.status_code == 200

    export_response = test_client.post(
        "/api/treatment/selection/export",
        json={"user_type": "kinetics", "ranges": "2 1"},
    )
    export_payload = export_response.get_json()

    assert export_response.status_code == 200
    assert export_payload["exported"]["user_type"] == "kinetics"

    output_path = Path(export_payload["exported"]["output_path"])
    assert output_path.is_file()

    saved = np.loadtxt(output_path)
    assert saved.shape == (4, 2)
    assert np.allclose(saved[:, 0], [1.0, 500.0, 550.0, 600.0])
    assert np.allclose(saved[:, 1], [2.0, 4.0, 5.0, 6.0])


def test_selection_export_writes_averaged_spectra_file(client):
    test_client, tmp_path = client
    abs_data = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    abs_path = tmp_path / "export_spectra.dat"
    _write_dat(
        abs_path,
        abs_data,
        wavelengths=[500, 550, 600],
        timedelays=[1, 2, 3],
    )

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(abs_path)},
    )
    assert assign_response.status_code == 200

    export_response = test_client.post(
        "/api/treatment/selection/export",
        json={"user_type": "spectra", "ranges": "550 60"},
    )
    export_payload = export_response.get_json()

    assert export_response.status_code == 200
    assert export_payload["exported"]["user_type"] == "spectra"

    output_path = Path(export_payload["exported"]["output_path"])
    assert output_path.is_file()

    saved = np.loadtxt(output_path)
    assert saved.shape == (4, 2)
    assert np.allclose(saved[:, 0], [50.0, 1.0, 2.0, 3.0])
    assert np.allclose(saved[:, 1], [550.0, 2.0, 5.0, 8.0])


def test_cleaning_sam_endpoint_returns_service_summary(client, monkeypatch):
    test_client, tmp_path = client
    data_file = tmp_path / "cleaning_input.dat"
    _write_dat(data_file, np.array([[1.0, 2.0], [3.0, 4.0]]))

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    assert assign_response.status_code == 200

    captured = {}

    def fake_analyze(session_id, session_state, angle_threshold, surface_threshold):
        captured["session_id"] = session_id
        captured["paths"] = dict(session_state["paths"])
        captured["angle_threshold"] = angle_threshold
        captured["surface_threshold"] = surface_threshold
        return {
            "file_path": str(data_file),
            "original_measurements": 10,
            "source_measurements": 10,
            "cleaned_measurements": 7,
            "removed_measurements": 3,
            "removed_in_pass": 3,
            "removed_by_angle": 2,
            "removed_by_surface": 1,
            "retention_rate": 70.0,
            "pass_retention_rate": 70.0,
            "average_surface": 42.0,
            "sam_angles_sample": [0.1, 0.2],
            "sam_angle_min": 0.1,
            "sam_angle_max": 0.4,
            "sam_angle_mean": 0.25,
            "kept_indices": [0, 1, 2],
            "state_updated": True,
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "analyze_sam_cleaning",
        fake_analyze,
    )
    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "get_cleaning_view",
        lambda _session_id, _session_state: {"current_measurements": 7},
    )

    response = test_client.post(
        "/api/treatment/cleaning/sam",
        json={"angle_threshold": 1.5, "surface_threshold": 5.0},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["session_id"]
    assert captured["paths"]["ABS"] == str(data_file)
    assert captured["angle_threshold"] == 1.5
    assert captured["surface_threshold"] == 5.0
    assert payload["cleaning"]["cleaned_measurements"] == 7
    assert payload["cleaning"]["sam_angle_mean"] == 0.25
    assert payload["cleaning_view"]["current_measurements"] == 7


def test_cleaning_view_endpoint_returns_service_preview(client, monkeypatch):
    test_client, tmp_path = client
    data_file = tmp_path / "cleaning_view_input.dat"
    _write_dat(data_file, np.array([[1.0, 2.0], [3.0, 4.0]]))

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    assert assign_response.status_code == 200

    captured = {}

    def fake_view(session_id, session_state):
        captured["session_id"] = session_id
        captured["paths"] = dict(session_state["paths"])
        return {
            "file_path": str(data_file),
            "cleaned_state": False,
            "current_measurements": 3,
            "original_measurements": 3,
            "shown_measurements": 3,
            "x": [1.0, 2.0],
            "traces": [{"index": 0, "y": [1.0, 2.0]}],
            "average": [2.0, 3.0],
            "y_axis_type": "linear",
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "get_cleaning_view",
        fake_view,
    )

    response = test_client.get("/api/treatment/cleaning/view")
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["session_id"]
    assert captured["paths"]["ABS"] == str(data_file)
    assert payload["cleaning_view"]["current_measurements"] == 3


def test_cleaning_reset_endpoint_clears_runtime_state(client, monkeypatch):
    test_client, tmp_path = client
    data_file = tmp_path / "cleaning_reset_input.dat"
    _write_dat(data_file, np.array([[1.0, 2.0], [3.0, 4.0]]))

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    assert assign_response.status_code == 200

    captured = {}

    def fake_reset(session_id, session_state):
        captured["session_id"] = session_id
        captured["paths"] = dict(session_state["paths"])
        return {
            "reset": True,
            "file_path": str(data_file),
            "discarded_measurements": 4,
            "original_measurements": 10,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "reset_sam_cleaning",
        fake_reset,
    )
    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "get_cleaning_view",
        lambda _session_id, _session_state: {"current_measurements": 10},
    )

    response = test_client.post("/api/treatment/cleaning/reset")
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["session_id"]
    assert captured["paths"]["ABS"] == str(data_file)
    assert payload["cleaning"]["reset"] is True
    assert payload["cleaning"]["discarded_measurements"] == 4
    assert payload["cleaning_view"]["current_measurements"] == 10


def test_cleaning_save_endpoint_returns_output_path(client, monkeypatch):
    test_client, tmp_path = client
    data_file = tmp_path / "cleaning_save_input.dat"
    _write_dat(data_file, np.array([[1.0, 2.0], [3.0, 4.0]]))

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(data_file)},
    )
    assert assign_response.status_code == 200

    saved_path = tmp_path / "abs_cleaned.h5"
    captured = {}

    def fake_save(session_id, session_state, angle_threshold, surface_threshold, output_file_name=""):
        captured["session_id"] = session_id
        captured["save_folder"] = session_state["save_folder"]
        captured["angle_threshold"] = angle_threshold
        captured["surface_threshold"] = surface_threshold
        captured["output_file_name"] = output_file_name
        saved_path.write_bytes(b"fake h5")
        return {
            "file_path": str(data_file),
            "output_path": str(saved_path),
            "original_measurements": 10,
            "source_measurements": 6,
            "cleaned_measurements": 6,
            "removed_measurements": 4,
            "removed_in_pass": 0,
            "removed_by_angle": 3,
            "removed_by_surface": 1,
            "retention_rate": 60.0,
            "pass_retention_rate": 100.0,
            "average_surface": 42.0,
            "sam_angles_sample": [0.1, 0.2],
            "sam_angle_min": 0.1,
            "sam_angle_max": 0.4,
            "sam_angle_mean": 0.25,
            "kept_indices": [0, 1],
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_sam_cleaned_h5",
        fake_save,
    )

    response = test_client.post(
        "/api/treatment/cleaning/save",
        json={
            "angle_threshold": 2.0,
            "surface_threshold": 10.0,
            "output_file_name": "abs_cleaned.h5",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["session_id"]
    assert captured["save_folder"] == str(tmp_path)
    assert captured["angle_threshold"] == 2.0
    assert captured["surface_threshold"] == 10.0
    assert captured["output_file_name"] == "abs_cleaned.h5"
    assert payload["cleaning"]["output_path"] == str(saved_path)
    assert payload["cleaning"]["assigned_data_type"] == "ABS"
    assert payload["cleaning"]["assigned_path"] == str(saved_path)
    assert payload["session"]["paths"]["ABS"] == str(saved_path)
    assert payload["session"]["path_sources"]["ABS"] == str(saved_path)


def test_cleaning_save_deletes_source_his_after_h5_is_written(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.his"
    source_file.write_bytes(b"fake his")

    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(source_file)},
    )
    assert assign_response.status_code == 200

    saved_path = tmp_path / "ABS12886.h5"

    def fake_save(session_id, session_state, angle_threshold, surface_threshold, output_file_name=""):
        saved_path.write_bytes(b"fake h5")
        return {
            "file_path": str(source_file),
            "source_file_path": str(source_file),
            "output_path": str(saved_path),
            "original_measurements": 10,
            "cleaned_measurements": 6,
            "removed_measurements": 4,
            "kept_indices": [0, 1, 2, 3, 4, 5],
            "removed_indices": [6, 7, 8, 9],
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_sam_cleaned_h5",
        fake_save,
    )

    response = test_client.post(
        "/api/treatment/cleaning/save",
        json={"angle_threshold": 2.0, "surface_threshold": 10.0},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert saved_path.is_file()
    assert not source_file.exists()
    assert payload["cleaning"]["deleted_source_file"] == str(source_file)
    assert payload["session"]["paths"]["ABS"] == str(saved_path)
    assert payload["session"]["path_sources"]["ABS"] == str(saved_path)


def test_cleaning_file_save_endpoint_uses_explicit_file_path(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "tree_file.h5"
    source_file.write_text("fake", encoding="ascii")
    saved_path = tmp_path / "tree_file_cleaned.h5"

    captured = {}

    def fake_save_file(file_path, angle_threshold, surface_threshold, output_file_name=""):
        captured["file_path"] = str(file_path)
        captured["angle_threshold"] = angle_threshold
        captured["surface_threshold"] = surface_threshold
        captured["output_file_name"] = output_file_name
        return {
            "file_path": str(file_path),
            "output_path": str(saved_path),
            "original_measurements": 10,
            "source_measurements": 10,
            "cleaned_measurements": 6,
            "removed_measurements": 4,
            "removed_in_pass": 4,
            "removed_by_angle": 3,
            "removed_by_surface": 1,
            "retention_rate": 60.0,
            "pass_retention_rate": 60.0,
            "average_surface": 42.0,
            "sam_angles_sample": [0.1, 0.2],
            "sam_angle_min": 0.1,
            "sam_angle_max": 0.4,
            "sam_angle_mean": 0.25,
            "kept_indices": [0, 1],
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_file_sam_cleaned_h5",
        fake_save_file,
    )

    response = test_client.post(
        "/api/treatment/cleaning/file/save",
        json={
            "file_path": str(source_file),
            "angle_threshold": 1.25,
            "surface_threshold": 7.5,
            "output_file_name": "tree_file_cleaned.h5",
        },
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["file_path"] == str(source_file)
    assert captured["angle_threshold"] == 1.25
    assert captured["surface_threshold"] == 7.5
    assert captured["output_file_name"] == "tree_file_cleaned.h5"
    assert payload["cleaning"]["output_path"] == str(saved_path)


def test_treatment_sessions_are_isolated_per_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(tmp_path))
    session_store.reset()

    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)

    abs_a = tmp_path / "abs_a.dat"
    abs_b = tmp_path / "abs_b.dat"
    _write_dat(abs_a, np.array([[1.0, 2.0], [3.0, 4.0]]))
    _write_dat(abs_b, np.array([[5.0, 6.0], [7.0, 8.0]]))

    client_a = app.test_client()
    client_b = app.test_client()
    try:
        session_a = client_a.get("/api/treatment/session").get_json()
        session_b = client_b.get("/api/treatment/session").get_json()

        assert session_a["session_id"] != session_b["session_id"]

        assign_a = client_a.post(
            "/api/treatment/session/path",
            json={"data_type": "ABS", "file_path": str(abs_a)},
        ).get_json()
        assign_b = client_b.post(
            "/api/treatment/session/path",
            json={"data_type": "ABS", "file_path": str(abs_b)},
        ).get_json()

        assert assign_a["session"]["paths"]["ABS"] == str(abs_a)
        assert assign_b["session"]["paths"]["ABS"] == str(abs_b)

        fresh_a = client_a.get("/api/treatment/session").get_json()
        fresh_b = client_b.get("/api/treatment/session").get_json()

        assert fresh_a["session"]["paths"]["ABS"] == str(abs_a)
        assert fresh_b["session"]["paths"]["ABS"] == str(abs_b)
    finally:
        client_a = None
        client_b = None


def test_treatment_sessions_are_isolated_per_header(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(tmp_path))
    session_store.reset()

    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)

    abs_v0 = tmp_path / "abs_v0.dat"
    abs_vd2 = tmp_path / "abs_vd2.dat"
    _write_dat(abs_v0, np.array([[1.0, 2.0], [3.0, 4.0]]))
    _write_dat(abs_vd2, np.array([[5.0, 6.0], [7.0, 8.0]]))

    session_v0_headers = {"X-Treatment-Session-Id": "browser:test:profile:v0"}
    session_vd2_headers = {"X-Treatment-Session-Id": "browser:test:profile:vd2"}

    with app.test_client() as test_client:
        session_v0 = test_client.get(
            "/api/treatment/session",
            headers=session_v0_headers,
        ).get_json()
        session_vd2 = test_client.get(
            "/api/treatment/session",
            headers=session_vd2_headers,
        ).get_json()

        assert session_v0["session_id"] != session_vd2["session_id"]
        assert session_v0["session_id"] == session_v0_headers["X-Treatment-Session-Id"]
        assert session_vd2["session_id"] == session_vd2_headers["X-Treatment-Session-Id"]

        test_client.post(
            "/api/treatment/session/path",
            headers=session_v0_headers,
            json={"data_type": "ABS", "file_path": str(abs_v0)},
        )
        test_client.post(
            "/api/treatment/session/path",
            headers=session_vd2_headers,
            json={"data_type": "ABS", "file_path": str(abs_vd2)},
        )

        fresh_v0 = test_client.get(
            "/api/treatment/session",
            headers=session_v0_headers,
        ).get_json()
        fresh_vd2 = test_client.get(
            "/api/treatment/session",
            headers=session_vd2_headers,
        ).get_json()

        assert fresh_v0["session"]["paths"]["ABS"] == str(abs_v0)
        assert fresh_vd2["session"]["paths"]["ABS"] == str(abs_vd2)
