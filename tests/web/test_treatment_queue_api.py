"""HTTP contracts for treatment queue recipe capture."""

import json
import sys
import time
from pathlib import Path
from threading import Event, Lock

import numpy as np
import pytest
from flask import Flask

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import treatment_api as treatment_api_module
from folder_api import folder_api
from treatment_api import TreatmentQueueStore, session_store, treatment_api
from treatment_manifest import TREATMENT_MANIFEST_FILE_NAME, TREATMENT_MANIFEST_FORMAT


def test_allowed_root_treats_windows_drive_paths_as_case_insensitive():
    assert treatment_api_module._is_within_local_path(
        r"E:\\DATA_VD2\\20260416\\12893-water\\ABS12893.h5",
        r"e:\\data_vd2",
    )
    assert not treatment_api_module._is_within_local_path(
        r"E:\\other_data\\12893-water\\ABS12893.h5",
        r"e:\\data_vd2",
    )


def test_treatment_worker_count_uses_up_to_six_available_cpus(monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_MAX_WORKERS", "6")
    monkeypatch.setattr(treatment_api_module.os, "cpu_count", lambda: 12)

    assert treatment_api_module._treatment_worker_count(10) == 6
    assert treatment_api_module._treatment_worker_count(3) == 3

    monkeypatch.setattr(treatment_api_module.os, "cpu_count", lambda: 4)
    assert treatment_api_module._treatment_worker_count(10) == 4

def _write_dat(path):
    wavelengths = np.asarray([500.0, 550.0])
    timedelays = np.asarray([1.0, 2.0])
    values = np.asarray([[1.0, 2.0], [3.0, 4.0]])
    payload = np.zeros((3, 3), dtype=float)
    payload[0, 1:] = wavelengths
    payload[1:, 0] = timedelays
    payload[1:, 1:] = values.T
    np.savetxt(path, payload, delimiter="\t", fmt="%.4f")


@pytest.fixture
def queue_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(tmp_path))
    session_store.reset()
    treatment_api_module.treatment_service.reset_runtime()
    monkeypatch.setattr(
        treatment_api_module, "treatment_queue_store", TreatmentQueueStore()
    )

    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)
    with app.test_client() as test_client:
        yield test_client, tmp_path, {"X-Treatment-Session-Id": "queue-contract"}
    deadline = time.monotonic() + 2.0
    while (
        treatment_api_module.treatment_queue_store.snapshot("queue-contract")["running"]
        and time.monotonic() < deadline
    ):
        time.sleep(0.005)


def _ready_session(test_client, tmp_path, headers, exp_type="ABS+BASE+NOISE"):
    response = test_client.post(
        "/api/treatment/session/config",
        json={
            "exp_type": exp_type,
            "save_folder": str(tmp_path),
            "save_file_name": "result.dat",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.get_json()

    role = "ABS+BASE+NOISE" if exp_type == "HIS" else None
    roles = [role] if role else ["ABS", "BASE", "NOISE"]
    for index, data_type in enumerate(roles):
        path = tmp_path / f"input-{index}.dat"
        _write_dat(path)
        response = test_client.post(
            "/api/treatment/session/path",
            json={"data_type": data_type, "file_path": str(path)},
            headers=headers,
        )
        assert response.status_code == 200, response.get_json()


def test_enqueue_freezes_recipe_and_autostarts_processing(
    queue_client, monkeypatch
):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    (tmp_path / "result.dat").write_text("previous output", encoding="utf-8")
    executor_calls = []
    entered = Event()
    release = Event()

    def capture_execute(job_id, recipe):
        executor_calls.append((job_id, recipe))
        entered.set()
        assert release.wait(2.0)
        return {
            "result": {"result_ready": True},
            "saved": None,
            "preparation": {},
        }

    monkeypatch.setattr(
        treatment_api_module, "_execute_treatment_queue_job", capture_execute
    )
    response = test_client.post(
        "/api/treatment/queue",
        json={
            "label": "sample-001",
            "convert_to_h5": True,
            "cleaning": {
                "enabled": True,
                "state": "pending",
                "angle_threshold": 1.5,
                "surface_threshold": 7.0,
                "data_types": ["ABS"],
            },
        },
        headers=headers,
    )
    payload = response.get_json()

    assert response.status_code == 200, payload
    recipe = payload["queue_job"]["recipe"]
    assert recipe["output"]["path"] == str(tmp_path / "result.dat")
    assert recipe["output"]["save_folder"] == str(tmp_path)
    assert recipe["output"]["save_file_name"] == "result.dat"
    assert recipe["output"]["archive_existing"] is True
    assert recipe["convert_to_h5"] == {"ABS": True, "BASE": True, "NOISE": True}
    assert recipe["cleaning"] == {
        "state": "pending",
        "enabled": True,
        "data_types": ["ABS"],
        "angle_threshold": 1.5,
        "surface_threshold": 7.0,
    }
    try:
        assert payload["started"] is True
        assert entered.wait(1.0)
        assert payload["queue"]["jobs"][0]["status"] in {"queued", "running"}
        assert executor_calls[0][1] == recipe

        # Mutating the live session after enqueue cannot alter the frozen recipe.
        test_client.post(
            "/api/treatment/session/config",
            json={"save_file_name": "changed.dat"},
            headers=headers,
        )
        snapshot = test_client.get("/api/treatment/queue", headers=headers).get_json()
        assert snapshot["queue"]["jobs"][0]["status"] == "running"
        assert snapshot["queue"]["jobs"][0]["recipe"] == recipe
        assert executor_calls[0][1]["output"]["save_file_name"] == "result.dat"
    finally:
        release.set()


def test_paired_his_queue_rejects_conversion_and_pending_cleaning(queue_client):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers, exp_type="HIS")

    conversion_response = test_client.post(
        "/api/treatment/queue",
        json={"convert_to_h5": True},
        headers=headers,
    )
    assert conversion_response.status_code == 400
    assert "paired" in conversion_response.get_json()["error"].lower()

    cleaning_response = test_client.post(
        "/api/treatment/queue",
        json={
            "cleaning": {
                "enabled": True,
                "state": "pending",
                "angle_threshold": 1.0,
                "surface_threshold": 1.0,
                "data_types": ["ABS+BASE+NOISE"],
            }
        },
        headers=headers,
    )
    assert cleaning_response.status_code == 400
    error = cleaning_response.get_json()["error"].lower()
    assert "independent abs, base, and noise" in error


def test_paired_his_queue_allows_direct_calculation_recipe(queue_client):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers, exp_type="HIS")

    response = test_client.post(
        "/api/treatment/queue",
        json={
            "label": "paired-direct",
            "convert_to_h5": False,
            "cleaning": {
                "enabled": False,
                "state": "not_requested",
                "data_types": [],
            },
        },
        headers=headers,
    )

    assert response.status_code == 200, response.get_json()
    recipe = response.get_json()["queue_job"]["recipe"]
    assert recipe["session"]["exp_type"] == "HIS"
    assert recipe["convert_to_h5"] == {"ABS+BASE+NOISE": False}


def test_standard_folder_queue_captures_destructive_vd2_recipe(queue_client):
    test_client, tmp_path, headers = queue_client
    folder = tmp_path / "12893-water_600_1us-x0"
    folder.mkdir()
    (folder / "ABS12893.his").write_bytes(b"abs")
    (folder / "BASE12893.his").write_bytes(b"base")
    (folder / "BRUIT12893.his").write_bytes(b"noise")

    response = test_client.post(
        "/api/treatment/queue/folder-set",
        json={
            "folder_path": str(folder),
            "allow_overwrite": True,
            "angle_threshold": 1.5,
            "surface_threshold": 7.0,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.get_json()
    recipe = response.get_json()["queue_job"]["recipe"]
    assert recipe["kind"] == "standard_folder_set"
    assert recipe["folder_set"] == {
        "folder_path": str(folder),
        "convert": True,
        "clean": True,
        "calculate": True,
        "angle_threshold": 1.5,
        "surface_threshold": 7.0,
    }
    assert recipe["output"]["path"] == str(tmp_path / "12893-water_600_1us-x0.dat")
    assert recipe["output"]["allow_overwrite"] is True
    assert recipe["provenance"]["source_his_policy"] == "delete_after_verified_h5"


@pytest.mark.parametrize(
    ("convert", "clean", "calculate"),
    [
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (True, False, True),
        (True, True, True),
    ],
)
def test_folder_queue_recipe_freezes_every_action_variant(
    queue_client, convert, clean, calculate
):
    _test_client, tmp_path, _headers = queue_client
    folder = tmp_path / f"variant-{int(convert)}-{int(clean)}-{int(calculate)}"
    folder.mkdir()
    (folder / "ABS100.his").write_bytes(b"abs")
    (folder / "BASE100.his").write_bytes(b"base")

    recipe = treatment_api_module._queue_standard_folder_recipe(
        "queue-contract",
        {
            "folder_path": str(folder),
            "convert": convert,
            "clean": clean,
            "calculate": calculate,
        },
    )

    assert recipe["folder_set"] == {
        "folder_path": str(folder),
        "convert": convert,
        "clean": clean,
        "calculate": calculate,
        "angle_threshold": 1.0,
        "surface_threshold": 1.0,
    }
    if calculate:
        assert recipe["output"]["save_file_name"] == f"{folder.name}.dat"
        assert recipe["output"]["path"] == str(tmp_path / f"{folder.name}.dat")
        assert recipe["output"]["archive_existing"] is True
    else:
        assert recipe["output"] == {}


def test_folder_queue_without_calc_does_not_save_dat(queue_client, monkeypatch):
    _test_client, tmp_path, _headers = queue_client
    folder = tmp_path / "set-only"
    folder.mkdir()
    (folder / "ABS101.his").write_bytes(b"abs")
    (folder / "BASE101.his").write_bytes(b"base")
    recipe = treatment_api_module._queue_standard_folder_recipe(
        "queue-contract",
        {
            "folder_path": str(folder),
            "convert": False,
            "clean": False,
            "calculate": False,
        },
    )
    monkeypatch.setattr(
        treatment_api_module,
        "_set_inputs_from_folder_job_payload",
        lambda _session_id, payload, progress_callback=None: {
            "folder_set": {
                "folder": payload["folder_path"],
                "calculate": payload["calculate"],
            }
        },
    )

    def fail_save(*_args, **_kwargs):
        raise AssertionError("Set-only folder jobs must not save DAT")

    monkeypatch.setattr(treatment_api_module, "_save_queued_result", fail_save)

    outcome = treatment_api_module._execute_standard_folder_queue_job(
        "set-only-job",
        recipe,
    )

    assert outcome["result"] is None
    assert outcome["saved"] is None
    assert not (tmp_path / "set-only.dat").exists()


def test_folder_enqueue_autostarts_once_and_drains_jobs_sequentially(
    queue_client, monkeypatch
):
    test_client, tmp_path, headers = queue_client
    folders = []
    for index in range(3):
        folder = tmp_path / f"queued-{index}"
        folder.mkdir()
        (folder / f"ABS{index}.his").write_bytes(b"abs")
        (folder / f"BASE{index}.his").write_bytes(b"base")
        folders.append(folder)

    first_started = Event()
    release_first = Event()
    guard = Lock()
    active = 0
    max_active = 0
    execution_order = []

    def fake_execute(_job_id, recipe):
        nonlocal active, max_active
        folder_path = recipe["folder_set"]["folder_path"]
        with guard:
            active += 1
            max_active = max(max_active, active)
            execution_order.append(folder_path)
            is_first = len(execution_order) == 1
        if is_first:
            first_started.set()
            assert release_first.wait(2.0)
        with guard:
            active -= 1
        return {
            "result": None,
            "saved": None,
            "preparation": {"folder_set": {"folder": folder_path}},
        }

    monkeypatch.setattr(
        treatment_api_module,
        "_execute_treatment_queue_job",
        fake_execute,
    )

    responses = []
    for folder in folders:
        responses.append(
            test_client.post(
                "/api/treatment/queue/folder-set",
                json={
                    "folder_path": str(folder),
                    "convert": False,
                    "clean": False,
                    "calculate": False,
                },
                headers=headers,
            )
        )
        if len(responses) == 1:
            assert first_started.wait(1.0)

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert [response.get_json()["started"] for response in responses] == [True, False, False]
    queued_snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")
    assert queued_snapshot["pending_count"] == 2
    assert [job["status"] for job in queued_snapshot["jobs"]] == [
        "running",
        "queued",
        "queued",
    ]

    release_first.set()
    deadline = time.monotonic() + 2.0
    snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")
    while snapshot["running"] and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")

    assert snapshot["running"] is False
    assert [job["status"] for job in snapshot["jobs"]] == ["completed"] * 3
    assert execution_order == [str(folder) for folder in folders]
    assert max_active == 1


def test_standard_folder_queue_honors_clean_setting(queue_client):
    test_client, tmp_path, headers = queue_client
    folder = tmp_path / "12893-water_600_1us-x1"
    folder.mkdir()
    (folder / "ABS12893.his").write_bytes(b"abs")
    (folder / "BASE12893.his").write_bytes(b"base")

    response = test_client.post(
        "/api/treatment/queue/folder-set",
        json={"folder_path": str(folder), "clean": False},
        headers=headers,
    )

    assert response.status_code == 200, response.get_json()
    assert response.get_json()["queue_job"]["recipe"]["folder_set"]["clean"] is False


def test_standard_folder_queue_archives_existing_dat_before_saving(queue_client, monkeypatch):
    test_client, tmp_path, headers = queue_client
    folder = tmp_path / "12895-water_600_1us-x0"
    folder.mkdir()
    (folder / "ABS12895.his").write_bytes(b"abs")
    (folder / "BASE12895.his").write_bytes(b"base")
    output_path = tmp_path / "12895-water_600_1us-x0.dat"
    output_path.write_text("previous output", encoding="utf-8")
    prior_backup = tmp_path / "12895-water_600_1us-x0_old1_1.dat"
    prior_backup.write_text("older output", encoding="utf-8")

    monkeypatch.setattr(
        treatment_api_module,
        "_set_inputs_from_folder_job_payload",
        lambda _session_id, payload, progress_callback=None: {
            "folder_set": {"folder": payload["folder_path"]},
            "result": {"result_ready": True},
        },
    )

    def save_result(_session_id, state):
        path = Path(state["save_folder"]) / state["save_file_name"]
        path.write_text("new output", encoding="utf-8")
        return {"save_path": str(path)}

    monkeypatch.setattr(treatment_api_module.treatment_service, "save_result", save_result)

    enqueue = test_client.post(
        "/api/treatment/queue/folder-set",
        json={"folder_path": str(folder)},
        headers=headers,
    )
    assert enqueue.status_code == 200, enqueue.get_json()
    started = test_client.post("/api/treatment/queue/run", headers=headers)
    assert started.status_code == 200, started.get_json()

    deadline = time.monotonic() + 2.0
    snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")
    while snapshot["running"] and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")

    assert snapshot["jobs"][0]["status"] == "completed"
    assert output_path.read_text(encoding="utf-8") == "new output"
    assert prior_backup.read_text(encoding="utf-8") == "older output"
    archived_path = tmp_path / "12895-water_600_1us-x0_old1_2.dat"
    assert archived_path.read_text(encoding="utf-8") == "previous output"
    assert snapshot["jobs"][0]["saved"]["archived_output_path"] == str(archived_path)


def test_standard_folder_queue_runs_folder_workflow_then_saves_dat(
    queue_client, monkeypatch
):
    test_client, tmp_path, headers = queue_client
    folder = tmp_path / "12894-water_600_1us-x0"
    folder.mkdir()
    (folder / "ABS12894.his").write_bytes(b"abs")
    (folder / "BASE12894.his").write_bytes(b"base")
    calls = []

    def fake_folder_set(session_id, payload, progress_callback=None):
        calls.append((session_id, payload))
        if progress_callback:
            progress_callback("complete", 2, 2, "Folder operation complete", {})
        return {
            "folder_set": {"folder": payload["folder_path"]},
            "result": {"result_ready": True},
        }

    monkeypatch.setattr(
        treatment_api_module,
        "_set_inputs_from_folder_job_payload",
        fake_folder_set,
    )
    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_result",
        lambda _session_id, state: {
            "save_path": str(Path(state["save_folder"]) / state["save_file_name"])
        },
    )

    enqueue = test_client.post(
        "/api/treatment/queue/folder-set",
        json={"folder_path": str(folder)},
        headers=headers,
    )
    assert enqueue.status_code == 200, enqueue.get_json()
    started = test_client.post("/api/treatment/queue/run", headers=headers)
    assert started.status_code == 200, started.get_json()

    deadline = time.monotonic() + 2.0
    snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")
    while snapshot["running"] and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")

    assert calls == [("queue-contract", snapshot["jobs"][0]["recipe"]["folder_set"])]
    assert snapshot["jobs"][0]["status"] == "completed"
    assert snapshot["jobs"][0]["saved"]["save_path"] == str(
        tmp_path / "12894-water_600_1us-x0.dat"
    )
    manifest_path = tmp_path / TREATMENT_MANIFEST_FILE_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["format"] == TREATMENT_MANIFEST_FORMAT
    assert manifest["format_version"] == 1
    assert manifest["dat_files"] == [
        {
            "dat_file": "12894-water_600_1us-x0.dat",
            "saved_at": manifest["dat_files"][0]["saved_at"],
            "workflow": {
                "kind": "standard_folder_set",
                "profile": "VD2",
                "label": "12894-water_600_1us-x0",
                "queue_job_id": snapshot["jobs"][0]["job_id"],
            },
            "session": {
                "experiment_type": "ABS+BASE+NOISE",
                "calculation_mode": "averaged",
                "first_map_with_electrons": True,
                "source_folder": str(folder),
            },
            "inputs": {},
            "processing": {"conversions": {}, "cleaning": {}},
            "result": {"save_path": str(tmp_path / "12894-water_600_1us-x0.dat")},
        }
    ]
    assert snapshot["jobs"][0]["saved"]["manifest_path"] == str(manifest_path)


def test_immediate_save_writes_and_upserts_manifest(queue_client, monkeypatch):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    save_path = str(tmp_path / "result.dat")

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_result",
        lambda _session_id, _state: {"save_path": save_path, "rows": 3, "cols": 3},
    )

    first = test_client.post("/api/treatment/save", headers=headers)
    second = test_client.post("/api/treatment/save", headers=headers)

    assert first.status_code == 200, first.get_json()
    assert second.status_code == 200, second.get_json()
    manifest_path = tmp_path / TREATMENT_MANIFEST_FILE_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["dat_files"]) == 1
    record = manifest["dat_files"][0]
    assert record["dat_file"] == "result.dat"
    assert record["workflow"]["kind"] == "immediate"
    assert record["inputs"]["ABS"]["source_path"] == str(tmp_path / "input-0.dat")
    assert record["inputs"]["BASE"]["source_path"] == str(tmp_path / "input-1.dat")
    assert record["inputs"]["NOISE"]["source_path"] == str(tmp_path / "input-2.dat")
    assert record["result"] == {"save_path": save_path, "rows": 3, "cols": 3}


def test_immediate_save_preserves_invalid_manifest(queue_client, monkeypatch):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    manifest_path = tmp_path / TREATMENT_MANIFEST_FILE_NAME
    manifest_path.write_text("not-json", encoding="utf-8")

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "save_result",
        lambda _session_id, _state: {"save_path": str(tmp_path / "result.dat")},
    )

    response = test_client.post("/api/treatment/save", headers=headers)

    assert response.status_code == 400
    assert "manifest is not valid JSON" in response.get_json()["error"]
    assert manifest_path.read_text(encoding="utf-8") == "not-json"


def test_autostart_exposes_completed_saved_receipt(queue_client, monkeypatch):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    expected_path = str(tmp_path / "result.dat")

    def fake_execute(_job_id, recipe):
        assert recipe["output"]["path"] == expected_path
        return {
            "result": {"result_ready": True},
            "saved": {"save_path": expected_path, "rows": 3, "cols": 3},
            "preparation": {"conversions": {}, "cleaned": {}},
        }

    monkeypatch.setattr(
        treatment_api_module, "_execute_treatment_queue_job", fake_execute
    )
    enqueue = test_client.post(
        "/api/treatment/queue",
        json={"label": "receipt"},
        headers=headers,
    )
    assert enqueue.status_code == 200, enqueue.get_json()
    assert enqueue.get_json()["started"] is True

    deadline = time.monotonic() + 2.0
    snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")
    while snapshot["running"] and time.monotonic() < deadline:
        time.sleep(0.005)
        snapshot = treatment_api_module.treatment_queue_store.snapshot("queue-contract")

    assert snapshot["running"] is False
    assert snapshot["jobs"][0]["status"] == "completed"
    assert snapshot["jobs"][0]["saved"]["save_path"] == expected_path


def test_failed_his_conversion_keeps_source_until_verified_h5_exists(
    queue_client, monkeypatch
):
    _test_client, tmp_path, _headers = queue_client
    source = tmp_path / "unverified.his"
    source.write_bytes(b"source")

    monkeypatch.setattr(
        treatment_api_module.treatment_service,
        "convert_file_to_h5",
        lambda *_args, **_kwargs: {"output_path": str(tmp_path / "unverified.h5")},
    )

    with pytest.raises(ValueError, match="H5 was not created"):
        treatment_api_module._convert_source_to_h5(str(source))
    assert source.is_file()


def test_immediate_save_rejects_output_reserved_by_running_job(
    queue_client, monkeypatch
):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    entered = Event()
    release = Event()

    def block_execute(_job_id, _recipe):
        entered.set()
        assert release.wait(2.0)
        return {"result": None, "saved": None, "preparation": {}}

    monkeypatch.setattr(
        treatment_api_module,
        "_execute_treatment_queue_job",
        block_execute,
    )

    enqueue_response = test_client.post(
        "/api/treatment/queue",
        json={"label": "queued-writer"},
        headers=headers,
    )
    assert enqueue_response.status_code == 200, enqueue_response.get_json()
    assert entered.wait(1.0)

    save_response = test_client.post("/api/treatment/save", headers=headers)
    payload = save_response.get_json()
    assert save_response.status_code == 400
    assert payload["success"] is False
    assert "already reserved" in payload["error"]
    release.set()


def test_failed_immediate_save_releases_reservation_for_retry(
    queue_client, monkeypatch
):
    test_client, tmp_path, headers = queue_client
    _ready_session(test_client, tmp_path, headers)
    calls = []

    def save_result(_session_id, _session_state):
        calls.append(True)
        if len(calls) == 1:
            raise ValueError("simulated save failure")
        return {"save_path": str(tmp_path / "result.dat")}

    monkeypatch.setattr(
        treatment_api_module.treatment_service, "save_result", save_result
    )

    first_response = test_client.post("/api/treatment/save", headers=headers)
    assert first_response.status_code == 400
    assert first_response.get_json()["error"] == "simulated save failure"

    retry_response = test_client.post("/api/treatment/save", headers=headers)
    assert retry_response.status_code == 200, retry_response.get_json()
    assert retry_response.get_json()["saved"]["save_path"] == str(
        tmp_path / "result.dat"
    )
    assert len(calls) == 2
