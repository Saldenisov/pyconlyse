import sys
from pathlib import Path

import numpy as np
import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from folder_api import folder_api
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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
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
            "suffix": ".md",
            "supported": False,
        },
        {
            "name": "signal.h5",
            "path": str(data_dir / "signal.h5"),
            "suffix": ".h5",
            "supported": h5_supported,
        },
    ]


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

    save_response = test_client.post("/api/treatment/save")
    save_payload = save_response.get_json()
    save_path = Path(save_payload["saved"]["save_path"])

    assert save_response.status_code == 200
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

    response = test_client.post("/api/treatment/cleaning/reset")
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["session_id"]
    assert captured["paths"]["ABS"] == str(data_file)
    assert payload["cleaning"]["reset"] is True
    assert payload["cleaning"]["discarded_measurements"] == 4


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
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
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
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
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
