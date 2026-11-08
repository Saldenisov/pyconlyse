"""Cases collected through test_treatment_service.py."""

if __package__:
    from .test_treatment_service import (
        FakeAverageOpener,
        FakePairOpener,
        Path,
        _critical_info,
        _measurement,
        _prepare_smb_result,
        np,
        pytest,
        treatment_service_module,
    )
else:
    from test_treatment_service import (
        FakeAverageOpener,
        FakePairOpener,
        Path,
        _critical_info,
        _measurement,
        _prepare_smb_result,
        np,
        pytest,
        treatment_service_module,
    )


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
    _prepare_smb_result(service, monkeypatch, tmp_path)
    temp_path = tmp_path / "smb-export.dat"
    handles = []

    def fake_named_temporary_file(**kwargs):
        assert kwargs == {"mode": "w", "suffix": ".dat", "delete": False}
        handle = open(temp_path, "w", encoding="utf-8")
        handles.append(handle)
        return handle

    copied = {}

    def fake_copy_local_file_to_smb_atomic(local_path, smb_path):
        assert len(handles) == 1
        assert handles[0].closed is True
        copied["smb_path"] = smb_path
        copied["payload"] = Path(local_path).read_text(encoding="utf-8")
        return len(copied["payload"].encode("utf-8"))

    monkeypatch.setattr(
        treatment_service_module.tempfile,
        "NamedTemporaryFile",
        fake_named_temporary_file,
    )
    monkeypatch.setattr(
        treatment_service_module,
        "copy_local_file_to_smb_atomic",
        fake_copy_local_file_to_smb_atomic,
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
    assert temp_path.exists() is False

def test_save_result_removes_smb_temp_file_when_copy_fails(service, monkeypatch, tmp_path):
    _prepare_smb_result(service, monkeypatch, tmp_path)
    temp_path = tmp_path / "smb-export-failure.dat"

    monkeypatch.setattr(
        treatment_service_module.tempfile,
        "NamedTemporaryFile",
        lambda **_kwargs: open(temp_path, "w", encoding="utf-8"),
    )

    def failing_copy(local_path, _smb_path):
        assert Path(local_path).exists()
        raise OSError("SMB copy failed")

    monkeypatch.setattr(
        treatment_service_module,
        "copy_local_file_to_smb_atomic",
        failing_copy,
    )

    with pytest.raises(OSError, match="SMB copy failed"):
        service.save_result(
            "session-save-smb",
            {
                "save_folder": "smb://10.20.30.202/e/DATA_VD2/20260127",
                "save_file_name": "water_test",
            },
        )

    assert temp_path.exists() is False
