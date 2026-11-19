"""Treatment api contracts."""

from tests.web._treatment_test_support import (
    FakeHisOpener,
    Flask,
    Path,
    _critical_info,
    _measurement,
    _write_dat,
    client,
    folder_api,
    folder_api_module,
    np,
    pytest,
    session_store,
    treatment_api,
    treatment_api_module,
)


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
