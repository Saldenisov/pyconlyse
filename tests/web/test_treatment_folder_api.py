"""Treatment folder api contracts."""

from tests.web._treatment_test_support import (
    Lock,
    Path,
    _write_dat,
    _write_gzip_h5,
    client,
    folder_api_module,
    np,
    pytest,
    time,
    treatment_api_module,
)


@pytest.mark.usefixtures("treatment_thread_executor")
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

    conversion_sizes = {}

    def fake_convert(source_path, output_path, progress_callback=None):
        _write_gzip_h5(output_path)
        conversion_sizes[str(output_path)] = Path(output_path).stat().st_size
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
        treatment_api_module.TreatmentDataService,
        "save_sam_cleaned_h5",
        lambda _self, *args, **kwargs: fake_save(*args, **kwargs),
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
    assert payload["folder_set"]["conversions"]["ABS"]["output_size_bytes"] == conversion_sizes[
        str(folder / "ABS12886.h5")
    ]
    assert payload["folder_set"]["conversions"]["ABS"]["space_change_bytes"] == (
        conversion_sizes[str(folder / "ABS12886.h5")] - len(b"abs his")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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


@pytest.mark.usefixtures("treatment_thread_executor")
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
        lambda path: path in {smb_root, f"{smb_root}/20260127", smb_folder},
    )
    monkeypatch.setattr(
        treatment_api_module,
        "smb_isdir",
        lambda path: path in {smb_root, f"{smb_root}/20260127", smb_folder},
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
        json={"exp_type": "ABS+BASE+NOISE", "calc_mode": "averaged"},
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
