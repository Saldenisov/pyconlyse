"""Treatment state survives a new server-process store instance."""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import treatment_api as treatment_api_module
from treatment_api import TreatmentQueueStore, TreatmentSessionStore, treatment_api
from treatment_state_repository import TreatmentStateRepository


@pytest.fixture
def repository(tmp_path):
    return TreatmentStateRepository(tmp_path / "treatment_state.sqlite3")


def test_session_config_folder_and_selection_survive_restart(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    folder = tmp_path / "experiment"
    folder.mkdir()
    source = folder / "ABS.h5"
    source.write_bytes(b"example input")
    store = TreatmentSessionStore(repository)
    store.set_folder("browser:one:profile:vd2", str(folder))
    store.update_config(
        "browser:one:profile:vd2",
        {"save_file_name": "manual.dat", "exp_type": "ABS+BASE+NOISE"},
    )
    store.set_data_path("browser:one:profile:vd2", "ABS", str(source))
    store.update_selection(
        "browser:one:profile:vd2",
        {"active_data_type": "ABS", "map_index": 3, "selection": {"x1": 4}},
    )

    restored = TreatmentSessionStore(repository).snapshot("browser:one:profile:vd2")
    assert restored["folder_path"] == str(folder)
    assert restored["save_folder"] == str(folder)
    assert restored["save_file_name"] == "manual.dat"
    assert restored["exp_type"] == "ABS+BASE+NOISE"
    assert restored["paths"]["ABS"] == str(source)
    assert restored["map_index"] == 3
    assert restored["selection"]["x1"] == 4


def test_session_reset_is_durable(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    store = TreatmentSessionStore(repository)
    store.update_config("browser:one:profile:vd2", {"save_file_name": "before.dat"})
    store.reset("browser:one:profile:vd2")
    assert TreatmentSessionStore(repository).snapshot("browser:one:profile:vd2")["save_file_name"] == ""


def test_queue_survives_restart_without_replaying_running_job(repository, tmp_path):
    store = TreatmentQueueStore(repository)
    active = store.enqueue("browser:one:profile:vd2", {"output": {"path": str(tmp_path / "active.dat")}})
    queued = store.enqueue("browser:one:profile:vd2", {"output": {"path": str(tmp_path / "queued.dat")}})
    store.update_job(active["job_id"], status="running", phase="converting")

    restored = TreatmentQueueStore(repository)
    snapshot = restored.snapshot("browser:one:profile:vd2")
    assert snapshot["persistence"] == "sqlite"
    assert snapshot["running"] is False
    assert snapshot["active_job_id"] is None
    assert snapshot["pending_count"] == 1
    assert [(job["job_id"], job["status"]) for job in snapshot["jobs"]] == [
        (active["job_id"], "interrupted"),
        (queued["job_id"], "queued"),
    ]
    with pytest.raises(ValueError, match="reserved"):
        restored.enqueue("browser:other:profile:vd2", {"output": {"path": str(tmp_path / "queued.dat")}})

    restarted_again = TreatmentQueueStore(repository)
    assert restarted_again.snapshot("browser:one:profile:vd2")["jobs"][0]["status"] == "interrupted"


def test_completed_queue_job_survives_restart(repository):
    store = TreatmentQueueStore(repository)
    job = store.enqueue("browser:one:profile:vd2", {"output": {}})
    assert store.start("browser:one:profile:vd2", lambda _job_id, _recipe: {
        "result": {"result_ready": True},
        "saved": {"save_path": "result.dat"},
        "preparation": {},
    }) is True
    deadline = time.monotonic() + 2
    while store.snapshot("browser:one:profile:vd2")["running"] and time.monotonic() < deadline:
        time.sleep(0.005)

    restored = TreatmentQueueStore(repository).snapshot("browser:one:profile:vd2")
    assert restored["jobs"][0]["job_id"] == job["job_id"]
    assert restored["jobs"][0]["status"] == "completed"
    assert restored["jobs"][0]["saved"]["save_path"] == "result.dat"


def test_browser_backup_restores_only_empty_session(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    folder = tmp_path / "experiment"
    folder.mkdir()
    source = folder / "ABS.h5"
    source.write_bytes(b"example input")
    store = TreatmentSessionStore(repository)
    backup = {
        "exp_type": "ABS+BASE+NOISE",
        "selected_data_type": "ABS",
        "active_data_type": "ABS",
        "map_index": 2,
        "selection": {"x1": 1, "x2": 2},
        "calc_mode": "averaged",
        "first_map_with_electrons": True,
        "folder_path": str(folder),
        "save_folder": str(folder),
        "save_file_name": "recovered.dat",
        "paths": {"ABS": str(source)},
        "path_sources": {"ABS": str(source)},
    }

    assert store.restore_if_empty("browser:one:profile:vd2", backup) is True
    assert store.snapshot("browser:one:profile:vd2")["paths"]["ABS"] == str(source)
    assert store.restore_if_empty("browser:one:profile:vd2", {**backup, "save_file_name": "stale.dat"}) is False
    assert TreatmentSessionStore(repository).snapshot("browser:one:profile:vd2")["save_file_name"] == "recovered.dat"


def test_browser_restore_endpoint_rejects_path_outside_root(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    monkeypatch.setattr(treatment_api_module, "session_store", TreatmentSessionStore(repository))
    app = Flask(__name__)
    app.register_blueprint(treatment_api)
    with app.test_client() as client:
        response = client.post(
            "/api/treatment/session/restore",
            headers={"X-Treatment-Session-Id": "browser:one:profile:vd2"},
            json={"session": {
                "exp_type": "ABS+BASE+NOISE",
                "selected_data_type": "ABS",
                "calc_mode": "averaged",
                "folder_path": str(tmp_path.parent),
            }},
        )
    assert response.status_code == 400
    assert "outside the allowed treatment root" in response.get_json()["error"]


@pytest.mark.parametrize("map_policy", ["selected_maps", "all_raw_maps"])
def test_calculated_result_is_rebuilt_from_persisted_inputs(
    repository, tmp_path, monkeypatch, map_policy
):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    store = TreatmentSessionStore(repository)
    store.mark_result_ready("browser:one:profile:vd2", True, map_policy)
    restored_store = TreatmentSessionStore(repository)
    monkeypatch.setattr(treatment_api_module, "session_store", restored_store)
    calls = []
    runtime = {"result_ready": False}

    def calc_abs(session_id, session_state):
        calls.append((session_id, session_state["result_ready"], session_state["include_excluded_maps"]))
        runtime["result_ready"] = True
        return {"result_ready": True}

    monkeypatch.setattr(
        treatment_api_module,
        "treatment_service",
        SimpleNamespace(
            supported_suffixes=(".h5",),
            runtime_status=lambda _session_id: dict(runtime),
            calc_abs=calc_abs,
        ),
    )

    first = treatment_api_module._session_payload("browser:one:profile:vd2")
    second = treatment_api_module._session_payload("browser:one:profile:vd2")
    assert first["session"]["result_ready"] is True
    assert second["session"]["result_ready"] is True
    assert first["session"]["result_map_policy"] == map_policy
    assert calls == [("browser:one:profile:vd2", True, map_policy == "all_raw_maps")]


def test_pending_cleaning_preview_is_rebuilt_after_restart(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(tmp_path))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    source = tmp_path / "ABS.h5"
    source.write_bytes(b"example input")
    store = TreatmentSessionStore(repository)
    store.set_data_path("browser:one:profile:vd2", "ABS", str(source))
    store.set_cleaning_preview_request("browser:one:profile:vd2", {
        "angle_threshold": 1.5,
        "surface_threshold": 7.0,
        "file_path": str(source),
    })
    monkeypatch.setattr(
        treatment_api_module,
        "session_store",
        TreatmentSessionStore(repository),
    )
    runtime = {"cleaning_ready": False, "cleaning_file_path": ""}
    calls = []

    def analyze(session_id, session_state, angle, surface):
        calls.append((session_id, session_state["paths"]["ABS"], angle, surface))
        runtime.update({"cleaning_ready": True, "cleaning_file_path": str(source)})
        return {"state_updated": True}

    monkeypatch.setattr(
        treatment_api_module,
        "treatment_service",
        SimpleNamespace(
            supported_suffixes=(".h5",),
            runtime_status=lambda _session_id: dict(runtime),
            analyze_sam_cleaning=analyze,
        ),
    )

    payload = treatment_api_module._session_payload("browser:one:profile:vd2")
    assert payload["session"]["cleaning_preview"]["ready"] is True
    assert calls == [("browser:one:profile:vd2", str(source), 1.5, 7.0)]
