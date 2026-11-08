"""Cases collected through test_treatment_api.py."""

if __package__:
    from .test_treatment_api import (
        Flask,
        Path,
        _write_dat,
        _write_gzip_h5,
        folder_api,
        np,
        pytest,
        session_store,
        treatment_api,
        treatment_api_module,
    )
else:
    from test_treatment_api import (
        Flask,
        Path,
        _write_dat,
        _write_gzip_h5,
        folder_api,
        np,
        pytest,
        session_store,
        treatment_api,
        treatment_api_module,
    )


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
        json={"user_type": "kinetics", "ranges": "550 60"},
    )
    export_payload = export_response.get_json()

    assert export_response.status_code == 200
    assert export_payload["exported"]["user_type"] == "kinetics"

    output_path = Path(export_payload["exported"]["output_path"])
    assert output_path.is_file()

    saved = np.loadtxt(output_path)
    assert saved.shape == (4, 2)
    assert np.allclose(saved[:, 0], [50.0, 1.0, 2.0, 3.0])
    assert np.allclose(saved[:, 1], [550.0, 4.0, 5.0, 6.0])

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
        json={"user_type": "spectra", "ranges": "2 1"},
    )
    export_payload = export_response.get_json()

    assert export_response.status_code == 200
    assert export_payload["exported"]["user_type"] == "spectra"

    output_path = Path(export_payload["exported"]["output_path"])
    assert output_path.is_file()

    saved = np.loadtxt(output_path)
    assert saved.shape == (4, 2)
    assert np.allclose(saved[:, 0], [1.0, 500.0, 550.0, 600.0])
    assert np.allclose(saved[:, 1], [2.0, 2.0, 5.0, 8.0])

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
        _write_gzip_h5(saved_path, compression_level=4)
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

def test_calc_abs_rejects_unapplied_cleaning_preview(client, monkeypatch):
    test_client, _tmp_path = client
    calc_calls = []

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "runtime_status",
        lambda _session_id: {"cleaning_ready": True},
    )

    def fail_if_called(*_args, **_kwargs):
        calc_calls.append(True)
        raise AssertionError("OD calculation must not run for a preview-only mask")

    monkeypatch.setattr(treatment_api_module.treatment_service, "calc_abs", fail_if_called)

    response = test_client.post("/api/treatment/calc-abs")
    payload = response.get_json()

    assert response.status_code == 400
    assert payload["success"] is False
    assert payload["error"] == "Cleaning preview is not applied; apply mask to H5 or reset preview."
    assert calc_calls == []

def test_session_exposes_transient_cleaning_preview_separately_from_persisted_masks(
    client, monkeypatch
):
    test_client, tmp_path = client
    source_file = tmp_path / "preview_contract.dat"
    _write_dat(source_file, np.ones((2, 2)))
    assign_response = test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(source_file)},
    )
    assert assign_response.status_code == 200

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "runtime_status",
        lambda _session_id: {
            "cleaning_ready": True,
            "cleaning_file_path": str(source_file),
            "cleaning_current_measurements": 6,
            "cleaning_original_measurements": 8,
        },
    )
    payload = test_client.get("/api/treatment/session").get_json()

    assert payload["session"]["cleaning_preview"] == {
        "ready": True,
        "file_path": str(source_file),
        "data_type": "ABS",
        "current_measurements": 6,
        "original_measurements": 8,
    }
    assert payload["session"]["map_selections"]["ABS"]["applied"] is False
    assert payload["session"]["map_selections"]["ABS"]["included_count"] is None

def test_cleaning_save_reassigns_role_and_reports_applied_map_mask(client, monkeypatch):
    h5py = treatment_api_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")

    test_client, tmp_path = client
    source_file = tmp_path / "abs_mask_source.dat"
    _write_dat(source_file, np.ones((2, 2)))
    assert test_client.post(
        "/api/treatment/session/path",
        json={"data_type": "ABS", "file_path": str(source_file)},
    ).status_code == 200
    saved_path = tmp_path / "abs_mask_applied.h5"

    def fake_save(*_args, **_kwargs):
        with h5py.File(saved_path, "w") as h5_file:
            h5_file.create_dataset("timedelays", data=np.asarray([1.0, 2.0]))
            h5_file.create_dataset("wavelengths", data=np.asarray([500.0, 550.0]))
            h5_file.create_dataset("raw_data", data=np.ones((2, 2, 2), dtype=float))
            selection = h5_file.create_group("map_selection")
            selection.create_dataset("included", data=np.asarray([True, False]))
            selection.attrs["method"] = "sam"
        return {
            "file_path": str(source_file),
            "output_path": str(saved_path),
            "original_measurements": 2,
            "cleaned_measurements": 1,
            "removed_measurements": 1,
        }

    monkeypatch.setattr(treatment_api_module.treatment_service, "save_sam_cleaned_h5", fake_save)
    response = test_client.post(
        "/api/treatment/cleaning/save",
        json={"angle_threshold": 1.0, "surface_threshold": 1.0},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["cleaning"]["assigned_path"] == str(saved_path)
    assert payload["session"]["paths"]["ABS"] == str(saved_path)
    assert payload["session"]["map_selections"]["ABS"] == {
        "applied": True,
        "included_count": 1,
        "total_count": 2,
        "method": "sam",
    }

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
