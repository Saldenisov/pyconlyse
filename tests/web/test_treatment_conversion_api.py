"""Treatment conversion api contracts."""

from tests.web._treatment_test_support import (
    Path,
    _write_gzip_h5,
    client,
    time,
    treatment_api_module,
)

import pytest


@pytest.mark.parametrize("conversion_fails", [False, True])
@pytest.mark.parametrize("endpoint", ["compress-file", "compress-path"])
def test_recompression_failure_retains_original_h5(client, monkeypatch, conversion_fails, endpoint):
    test_client, tmp_path = client
    source = tmp_path / "ABS-original.h5"
    original = b"original recording"
    source.write_bytes(original)

    def incomplete_conversion(source_path, output_path, progress_callback=None):
        assert Path(source_path) == source
        assert Path(output_path) != source
        Path(output_path).write_bytes(b"partial H5")
        if conversion_fails:
            raise OSError("conversion interrupted")
        return {"output_path": str(output_path)}

    monkeypatch.setattr(treatment_api_module.treatment_service, "convert_file_to_h5", incomplete_conversion)
    response = test_client.post(
        f"/api/treatment/session/{endpoint}",
        json={"file_path": str(source), "data_type": "ABS"},
    )

    assert response.status_code == 400, response.get_json()
    assert source.read_bytes() == original
    assert list(tmp_path.iterdir()) == [source]
    assert response.get_json()["success"] is False
    assert test_client.get("/api/treatment/session").get_json()["session"]["paths"] == {}


def test_cache_copy_failure_returns_json_and_retains_session(client, monkeypatch):
    test_client, tmp_path = client
    source = tmp_path / "ABS-original.h5"
    source.write_bytes(b"original recording")

    def failed_cache(_source):
        raise OSError("cache disk is full")

    monkeypatch.setattr(treatment_api_module, "_cache_assignable_source", failed_cache)
    response = test_client.post(
        "/api/treatment/session/cache-path",
        json={"file_path": str(source), "data_type": "ABS"},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "cache disk is full"
    assert test_client.get("/api/treatment/session").get_json()["session"]["paths"] == {}
    assert source.read_bytes() == b"original recording"


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
        assert Path(source_path) == source_file
        assert Path(output_path) != source_file
        assert Path(output_path).parent.parent == source_file.parent
        assert source_file.read_bytes() == b"old h5 payload"
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(output_path, compression_level=4)
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
    assert response.status_code == 200, payload
    cached_path = Path(payload["cached_file"]["cached_path"])
    assert treatment_api_module.h5py.is_hdf5(source_file)
    assert cached_path.read_bytes() == source_file.read_bytes()
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
        assert Path(source_path) == source_file
        assert Path(output_path) != source_file
        assert Path(output_path).parent.parent == source_file.parent
        assert source_file.read_bytes() == b"old h5 payload"
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(output_path, compression_level=4)
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
    assert treatment_api_module.h5py.is_hdf5(source_file)
    assert payload["conversion"]["overwritten"] is True
    assert payload["session"]["paths"] == {}
    assert payload["session"]["path_sources"] == {}


def test_compress_file_start_reports_job_progress(client, monkeypatch):
    test_client, tmp_path = client
    source_file = tmp_path / "ABS12886.h5"
    source_file.write_bytes(b"old h5 payload")

    def fake_convert(source_path, output_path, progress_callback=None):
        assert Path(source_path) == source_file
        assert Path(output_path) != source_file
        assert Path(output_path).parent.parent == source_file.parent
        assert source_file.read_bytes() == b"old h5 payload"
        if progress_callback:
            progress_callback(1, 1)
        _write_gzip_h5(output_path, compression_level=4)
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
