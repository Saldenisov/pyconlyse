"""Treatment analysis api contracts."""

from tests.web._treatment_test_support import (
    Path,
    _write_dat,
    client,
    json,
    np,
    pytest,
    treatment_api_module,
)


def test_spectral_mode_requires_current_abs_reference_and_calculates_after_selection(client):
    test_client, tmp_path = client
    configured = test_client.post(
        "/api/treatment/session/config",
        json={"exp_type": "ABS+BASE+NOISE", "calc_mode": "matched_spectral_sum"},
    )
    assert configured.status_code == 200, configured.get_json()
    for role, data in (("ABS", [[10, 5], [20, 10]]),
                       ("BASE", [[10, 10], [20, 20]]),
                       ("NOISE", [[0, 0], [0, 0]])):
        path = tmp_path / f"{role}.dat"
        _write_dat(path, data)
        response = test_client.post(
            "/api/treatment/session/path", json={"data_type": role, "file_path": str(path)},
        )
        assert response.status_code == 200, response.get_json()

    rejected = test_client.post("/api/treatment/calc-abs")
    assert rejected.status_code == 400
    assert "reference window" in rejected.get_json()["error"]
    selected = test_client.post(
        "/api/treatment/session/config",
        json={"spectral_reference": {"source": str(tmp_path / "ABS.dat"), "start": 0, "stop": 1}},
    )
    assert selected.status_code == 200, selected.get_json()
    calculated = test_client.post("/api/treatment/calc-abs")
    assert calculated.status_code == 200, calculated.get_json()
    np.testing.assert_allclose(calculated.get_json()["result"]["sample"], [[0, np.log10(2)], [0, np.log10(2)]])


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
        json={"exp_type": "ABS+BASE+NOISE", "calc_mode": "averaged", "save_file_name": "od_result.dat"},
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
    assert view_payload["selection"]["kinetics"]["x"] == [1.0, 2.0, 3.0]
    assert view_payload["selection"]["kinetics"]["y"] == [4.0, 5.0, 6.0]
    assert view_payload["selection"]["spectrum"]["x"] == [500.0, 550.0, 600.0]
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
