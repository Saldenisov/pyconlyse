"""Cases collected through test_treatment_api.py."""

if __package__:
    from .test_treatment_api import (
        Barrier,
        Lock,
        Path,
        ThreadPoolExecutor,
        _write_dat,
        _write_gzip_h5,
        folder_api_module,
        np,
        pytest,
        time,
        treatment_api_module,
    )
else:
    from test_treatment_api import (
        Barrier,
        Lock,
        Path,
        ThreadPoolExecutor,
        _write_dat,
        _write_gzip_h5,
        folder_api_module,
        np,
        pytest,
        time,
        treatment_api_module,
    )


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
        _write_gzip_h5(output_path)
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
    assert cached_path.read_bytes() == output_file.read_bytes()
    assert payload["conversion"]["converted"] is True
    assert payload["conversion"]["deleted_source"] is True
    assert payload["conversion"]["source_size_bytes"] == len(b"fake his payload")
    assert payload["conversion"]["output_size_bytes"] == output_file.stat().st_size
    assert payload["session"]["paths"]["ABS"] == str(cached_path)
    assert payload["session"]["path_sources"]["ABS"] == str(output_file)

def test_compress_and_assign_overwrites_h5_without_deleting_source(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) != Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(Path(output_path), compression_level=4)
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
    assert cached_path.read_bytes() == source_file.read_bytes()
    with treatment_api_module.h5py.File(source_file, "r") as h5_file:
        assert h5_file["raw_data"].compression_opts == 4
    assert payload["conversion"]["converted"] is True
    assert payload["conversion"]["overwritten"] is True
    assert payload["conversion"]["deleted_source"] is False
    assert payload["conversion"]["source_size_bytes"] == len(b"old h5 payload")
    assert payload["conversion"]["output_size_bytes"] == source_file.stat().st_size
    assert payload["session"]["path_sources"]["ABS"] == str(source_file)

def test_compress_file_endpoint_does_not_assign_input(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) != Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(Path(output_path), compression_level=4)
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
    with treatment_api_module.h5py.File(source_file, "r") as h5_file:
        assert h5_file["raw_data"].compression_opts == 4
    assert payload["conversion"]["overwritten"] is True
    assert payload["session"]["paths"] == {}
    assert payload["session"]["path_sources"] == {}

def test_compress_file_start_reports_job_progress(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) != Path(output_path)
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(Path(output_path), compression_level=4)
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
    assert job["conversion"]["output_size_bytes"] == source_file.stat().st_size
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

def test_compress_h5_keeps_source_when_staged_output_is_invalid(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"original h5 payload")

    def fake_convert(_source_path, output_path, progress_callback=None):
        Path(output_path).write_bytes(b"invalid compressed h5")
        return {"output_path": str(output_path)}

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-file",
        json={"file_path": str(source_file)},
    )

    assert response.status_code == 400
    assert "verification failed" in response.get_json()["error"]
    assert source_file.read_bytes() == b"original h5 payload"

def test_compress_keeps_his_when_output_h5_verification_fails(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.his"
    source_file.write_bytes(b"his source")

    def fake_convert(_source_path, output_path, progress_callback=None):
        Path(output_path).write_bytes(b"not an h5 file")
        return {"output_path": str(output_path)}

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        fake_convert,
    )

    response = test_client.post(
        "/api/treatment/session/compress-file",
        json={"file_path": str(source_file)},
    )

    assert response.status_code == 400
    assert "verification failed" in response.get_json()["error"]
    assert source_file.is_file()

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
    both_cleaning = Barrier(2, timeout=3)

    def fake_clean_worker(
        data_type, session_state, angle_threshold, surface_threshold,
        output_file_name, _progress_queue,
    ):
        both_cleaning.wait()
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
    monkeypatch.setenv("PYCONLYSE_TREATMENT_MAX_WORKERS", "2")
    monkeypatch.setattr(treatment_api_module, "_queue_clean_worker", fake_clean_worker)

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

def test_folder_set_without_clean_calculates_all_maps_and_preserves_h5_masks(client):
    h5py = treatment_api_module.h5py
    if h5py is None:
        pytest.skip("h5py is not available")
    test_client, tmp_path = client
    folder = tmp_path / "uncleaned"
    folder.mkdir()

    for name, values in (
        ("ABS1.h5", [1.0, 10.0]),
        ("BASE1.h5", [10.0, 10.0]),
        ("NOISE1.h5", [0.0, 0.0]),
    ):
        with h5py.File(folder / name, "w") as h5_file:
            metadata = h5_file.create_group("metadata")
            metadata.attrs["time_scale"] = "ps"
            h5_file.create_dataset("timedelays", data=[1.0, 2.0])
            h5_file.create_dataset("wavelengths", data=[500.0, 550.0])
            h5_file.create_dataset(
                "raw_data",
                data=np.asarray([np.full((2, 2), value) for value in values]),
                compression="gzip",
                compression_opts=4,
            )
            selection = h5_file.create_group("map_selection")
            selection.create_dataset("included", data=[True, False])

    config = test_client.post(
        "/api/treatment/session/config", json={"exp_type": "ABS+BASE+NOISE"}
    )
    assert config.status_code == 200, config.get_json()
    response = test_client.post(
        "/api/treatment/session/folder-set",
        json={"folder_path": str(folder), "convert": True, "clean": False, "calculate": True},
    )
    payload = response.get_json()

    assert response.status_code == 200, payload
    assert payload["folder_set"]["map_policy"] == "all_raw_maps"
    assert payload["folder_set"]["map_counts"]["ABS"] == {
        "total_count": 2,
        "used_count": 2,
        "stored_mask_included_count": 1,
    }
    assert payload["folder_set"]["auto_calculated"] is True
    assert payload["result"]["mean"] == pytest.approx(np.log10(10.0 / 5.5))
    with h5py.File(folder / "ABS1.h5", "r") as h5_file:
        assert h5_file["map_selection"]["included"][:].tolist() == [True, False]

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
    monkeypatch.setattr(
        treatment_api_module,
        "_cpu_executor",
        lambda worker_count: ThreadPoolExecutor(max_workers=worker_count),
    )
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
