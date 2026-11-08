import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
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


def test_dat_preview_preserves_input_roles_and_opens_selection(client, tmp_path):
    client, tmp_path = client
    source = tmp_path / 'inspect.dat'
    _write_dat(source, [[0.1, 0.2], [0.3, 0.4]])
    headers = {'X-Treatment-Session-Id': 'dat-preview-test'}
    client.get('/api/treatment/session', headers=headers)
    input_path = tmp_path / 'abs-input.dat'
    _write_dat(input_path, [[10, 20], [30, 40]])
    session_store.set_data_path('dat-preview-test', 'ABS', str(input_path))
    original = session_store.snapshot('dat-preview-test')
    response = client.post('/api/treatment/preview/dat', json={'file_path': str(source)}, headers=headers)
    assert response.status_code == 200, response.get_json()
    state = session_store.snapshot('dat-preview-test')
    assert state['paths'] == original['paths']
    assert state['save_file_name'] == original['save_file_name']
    assert state['active_data_type'] == 'DAT'
    selected = client.get('/api/treatment/selection', headers=headers).get_json()['selection']
    assert selected['active_data_type'] == 'DAT'
    assert selected['assigned_data_types'] == ['DAT', 'ABS']
    assert treatment_api_module.treatment_service._resolve_active_path(state) == ('ABS', input_path)
    assert selected['selection_ready'] is True
    assert session_store.restore_if_empty('restored-dat-preview', state)
    assert session_store.snapshot('restored-dat-preview')['dat_preview_path'] == state['dat_preview_path']
    bad = client.post('/api/treatment/preview/dat', json={'file_path': str(tmp_path / 'abs.h5')}, headers=headers)
    assert bad.status_code != 200
    assert session_store.snapshot('dat-preview-test')['dat_preview_path'] == state['dat_preview_path']
    broken = tmp_path / 'invalid.dat'
    broken.write_text('1 2 3')
    bad = client.post('/api/treatment/preview/dat', json={'file_path': str(broken)}, headers=headers)
    assert bad.status_code == 400
    assert session_store.snapshot('dat-preview-test')['dat_preview_path'] == state['dat_preview_path']


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
        selection = h5_file.create_group("map_selection")
        selection.create_dataset("included", data=np.ones(2, dtype=bool))
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
    # Contract tests inject in-process fake converters; production uses processes.
    monkeypatch.setattr(
        treatment_api_module,
        "_cpu_executor",
        lambda worker_count: ThreadPoolExecutor(max_workers=worker_count),
    )
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
    assert payload["session"]["save_folder"] == str(data_dir)
    assert payload["session"]["save_file_name"] == "run_001.dat"

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


def test_selecting_another_folder_replaces_manual_save_folder(client):
    test_client, root = client
    first = root / "first"
    second = root / "second"
    manual = root / "manual"
    for folder in (first, second, manual):
        folder.mkdir()

    response = test_client.post(
        "/api/treatment/session/folder", json={"folder_path": str(first)}
    )
    assert response.status_code == 200
    assert response.get_json()["session"]["save_folder"] == str(first)

    response = test_client.post(
        "/api/treatment/session/config", json={"save_folder": str(manual)}
    )
    assert response.status_code == 200
    assert response.get_json()["session"]["save_folder"] == str(manual)

    response = test_client.post(
        "/api/treatment/session/folder", json={"folder_path": str(second)}
    )
    assert response.status_code == 200
    assert response.get_json()["session"]["folder_path"] == str(second)
    assert response.get_json()["session"]["save_folder"] == str(second)
    assert response.get_json()["session"]["save_file_name"] == "second.dat"


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


def test_changing_root_preserves_other_workspace_state_and_runtime(client, monkeypatch):
    test_client, tmp_path = client
    other_id = "browser:one:profile:vd2:workspace:other"
    session_store.update_config(other_id, {"save_file_name": "preserved.dat"})
    before = session_store.snapshot(other_id)
    resets = []
    monkeypatch.setattr(treatment_api_module.treatment_service, "reset_runtime", resets.append)
    new_root = tmp_path / "VD2"
    new_root.mkdir()

    response = test_client.post(
        "/api/treatment/session/root",
        headers={"X-Treatment-Session-Id": "browser:one:profile:vd2:workspace:new"},
        json={"allowed_root": str(new_root)},
    )

    assert response.status_code == 200
    assert session_store.snapshot(other_id) == before
    assert resets == ["browser:one:profile:vd2:workspace:new"]


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


# Keep the original pytest entry point and assertion diagnostics.
pytest.register_assert_rewrite(
    f"{__package__}._treatment_api_assign_file_and_update_cases" if __package__ else "_treatment_api_assign_file_and_update_cases",
    f"{__package__}._treatment_api_folder_set_convert_replaces_cases" if __package__ else "_treatment_api_folder_set_convert_replaces_cases",
    f"{__package__}._treatment_api_selection_export_writes_averaged_cases" if __package__ else "_treatment_api_selection_export_writes_averaged_cases",
)

if __package__:
    from ._treatment_api_assign_file_and_update_cases import (
        test_assign_file_and_update_config,
        test_cache_and_assign_copies_file_to_server_cache,
        test_cache_and_assign_copies_smb_file_to_server_cache,
        test_compress_and_assign_converts_his_to_h5_and_deletes_source,
        test_compress_and_assign_overwrites_h5_without_deleting_source,
        test_compress_file_endpoint_does_not_assign_input,
        test_compress_file_start_reports_job_progress,
        test_compress_file_skips_existing_gzip_h5,
        test_compress_h5_keeps_source_when_staged_output_is_invalid,
        test_compress_keeps_his_when_output_h5_verification_fails,
        test_folder_set_convert_clean_deletes_his_and_assigns_cleaned_h5,
        test_folder_set_without_clean_calculates_all_maps_and_preserves_h5_masks,
        test_folder_set_his_noise_allows_abs_base_without_folder_noise,
        test_folder_set_abs_base_noise_requires_abs_and_base_not_noise,
        test_folder_set_convert_runs_conversions_in_parallel,
        test_smb_folder_convert_stages_io_and_converts_locally_in_parallel,
    )
else:
    from _treatment_api_assign_file_and_update_cases import (
        test_assign_file_and_update_config,
        test_cache_and_assign_copies_file_to_server_cache,
        test_cache_and_assign_copies_smb_file_to_server_cache,
        test_compress_and_assign_converts_his_to_h5_and_deletes_source,
        test_compress_and_assign_overwrites_h5_without_deleting_source,
        test_compress_file_endpoint_does_not_assign_input,
        test_compress_file_start_reports_job_progress,
        test_compress_file_skips_existing_gzip_h5,
        test_compress_h5_keeps_source_when_staged_output_is_invalid,
        test_compress_keeps_his_when_output_h5_verification_fails,
        test_folder_set_convert_clean_deletes_his_and_assigns_cleaned_h5,
        test_folder_set_without_clean_calculates_all_maps_and_preserves_h5_masks,
        test_folder_set_his_noise_allows_abs_base_without_folder_noise,
        test_folder_set_abs_base_noise_requires_abs_and_base_not_noise,
        test_folder_set_convert_runs_conversions_in_parallel,
        test_smb_folder_convert_stages_io_and_converts_locally_in_parallel,
    )

if __package__:
    from ._treatment_api_folder_set_convert_replaces_cases import (
        test_folder_set_convert_replaces_existing_gzip_h5_from_his,
        test_folder_set_convert_mixed_h5_and_his_converts_remaining_his,
        test_folder_set_his_noise_mode_detects_separate_abs_base_folder,
        test_folder_set_start_reports_job_progress,
        test_folder_set_start_rejects_concurrent_session_operation,
        test_auto_assign_smb_folder_caches_abs_base_bruit_his,
        test_his_cache_preview_calculate_and_save_flow,
        test_auto_assign_abs_base_noise_files_from_current_folder,
        test_folder_set_auto_calculates_od_when_inputs_ready,
        test_auto_assign_his_noise_uses_abs_base_plus_noise,
        test_rejects_selected_data_type_incompatible_with_exp_type,
        test_rejects_paths_outside_allowed_root,
        test_preview_and_calc_abs_work_with_server_local_files,
        test_selection_view_uses_active_file_and_cursor_ranges,
        test_assigning_new_file_preserves_selection_cursors,
    )
else:
    from _treatment_api_folder_set_convert_replaces_cases import (
        test_folder_set_convert_replaces_existing_gzip_h5_from_his,
        test_folder_set_convert_mixed_h5_and_his_converts_remaining_his,
        test_folder_set_his_noise_mode_detects_separate_abs_base_folder,
        test_folder_set_start_reports_job_progress,
        test_folder_set_start_rejects_concurrent_session_operation,
        test_auto_assign_smb_folder_caches_abs_base_bruit_his,
        test_his_cache_preview_calculate_and_save_flow,
        test_auto_assign_abs_base_noise_files_from_current_folder,
        test_folder_set_auto_calculates_od_when_inputs_ready,
        test_auto_assign_his_noise_uses_abs_base_plus_noise,
        test_rejects_selected_data_type_incompatible_with_exp_type,
        test_rejects_paths_outside_allowed_root,
        test_preview_and_calc_abs_work_with_server_local_files,
        test_selection_view_uses_active_file_and_cursor_ranges,
        test_assigning_new_file_preserves_selection_cursors,
    )

if __package__:
    from ._treatment_api_selection_export_writes_averaged_cases import (
        test_selection_export_writes_averaged_kinetics_file,
        test_selection_export_writes_averaged_spectra_file,
        test_cleaning_sam_endpoint_returns_service_summary,
        test_cleaning_view_endpoint_returns_service_preview,
        test_cleaning_reset_endpoint_clears_runtime_state,
        test_cleaning_save_endpoint_returns_output_path,
        test_cleaning_save_deletes_source_his_after_h5_is_written,
        test_cleaning_file_save_endpoint_uses_explicit_file_path,
        test_calc_abs_rejects_unapplied_cleaning_preview,
        test_session_exposes_transient_cleaning_preview_separately_from_persisted_masks,
        test_cleaning_save_reassigns_role_and_reports_applied_map_mask,
        test_treatment_sessions_are_isolated_per_client,
        test_treatment_sessions_are_isolated_per_header,
    )
else:
    from _treatment_api_selection_export_writes_averaged_cases import (
        test_selection_export_writes_averaged_kinetics_file,
        test_selection_export_writes_averaged_spectra_file,
        test_cleaning_sam_endpoint_returns_service_summary,
        test_cleaning_view_endpoint_returns_service_preview,
        test_cleaning_reset_endpoint_clears_runtime_state,
        test_cleaning_save_endpoint_returns_output_path,
        test_cleaning_save_deletes_source_his_after_h5_is_written,
        test_cleaning_file_save_endpoint_uses_explicit_file_path,
        test_calc_abs_rejects_unapplied_cleaning_preview,
        test_session_exposes_transient_cleaning_preview_separately_from_persisted_masks,
        test_cleaning_save_reassigns_role_and_reports_applied_map_mask,
        test_treatment_sessions_are_isolated_per_client,
        test_treatment_sessions_are_isolated_per_header,
    )
