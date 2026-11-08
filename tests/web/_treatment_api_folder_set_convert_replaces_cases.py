"""Cases collected through test_treatment_api.py."""

if __package__:
    from .test_treatment_api import (
        FakeHisOpener,
        Path,
        _critical_info,
        _measurement,
        _write_dat,
        _write_gzip_h5,
        folder_api_module,
        np,
        time,
        treatment_api_module,
    )
else:
    from test_treatment_api import (
        FakeHisOpener,
        Path,
        _critical_info,
        _measurement,
        _write_dat,
        _write_gzip_h5,
        folder_api_module,
        np,
        time,
        treatment_api_module,
    )


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
        _write_gzip_h5(output_path, compression_level=4)
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
    assert abs_h5.is_file()
    assert base_h5.is_file()
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
        _write_gzip_h5(output_path, compression_level=4)
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
    assert base_h5.is_file()
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
        _write_gzip_h5(output_path, compression_level=4)
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
    assert base_h5.is_file()
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

def test_folder_set_start_rejects_concurrent_session_operation(client, monkeypatch):
    test_client, tmp_path = client

    def slow_folder_operation(*_args, **_kwargs):
        time.sleep(0.2)
        return {"folder_set": {}}

    monkeypatch.setattr(
        treatment_api_module,
        "_set_inputs_from_folder_job_payload",
        slow_folder_operation,
    )

    first = test_client.post(
        "/api/treatment/session/folder-set/start",
        json={"folder_path": str(tmp_path)},
    )
    second = test_client.post(
        "/api/treatment/session/folder-set/start",
        json={"folder_path": str(tmp_path)},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert "already running" in second.get_json()["error"]

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
    assert payload["session"]["save_folder"] == smb_folder
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
    assert view_payload["selection"]["kinetics"]["x"] == [1.0, 2.0, 3.0]
    assert view_payload["selection"]["kinetics"]["y"] == [4.0, 5.0, 6.0]
    assert view_payload["selection"]["spectrum"]["x"] == [500.0, 550.0, 600.0]
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
