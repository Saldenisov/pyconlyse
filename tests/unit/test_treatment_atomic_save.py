"""Atomic result-save and software-only queue execution contracts."""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import treatment_service as treatment_service_module
from treatment_service import TreatmentDataService


def _service_with_result():
    service = TreatmentDataService()
    info = SimpleNamespace(
        wavelengths=np.asarray([500.0, 550.0]),
        timedelays=np.asarray([1.0, 2.0]),
        scaling_yunit="ps",
    )
    service._runtimes["save-test"] = {
        **service._empty_runtime(),
        "result": np.asarray([[1.0, 2.0], [3.0, 4.0]]),
        "result_info": info,
    }
    return service


def test_save_result_replaces_local_target_atomically_without_temp_file(tmp_path):
    service = _service_with_result()
    target = tmp_path / "result.dat"
    target.write_text("old result\n", encoding="utf-8")
    before = set(tmp_path.iterdir())

    saved = service.save_result(
        "save-test",
        {"save_folder": str(tmp_path), "save_file_name": "result.dat"},
    )

    assert saved["save_path"] == str(target)
    assert saved["bytes"] == target.stat().st_size
    assert target.read_text(encoding="utf-8") != "old result\n"
    assert set(tmp_path.iterdir()) == before


def test_save_result_write_failure_preserves_old_target_and_cleans_temp(
    tmp_path, monkeypatch
):
    service = _service_with_result()
    target = tmp_path / "result.dat"
    target.write_text("old result\n", encoding="utf-8")
    before = set(tmp_path.iterdir())

    def fail_savetxt(*_args, **_kwargs):
        raise OSError("simulated write failure")

    monkeypatch.setattr(treatment_service_module.np, "savetxt", fail_savetxt)
    with pytest.raises(OSError, match="simulated write failure"):
        service.save_result(
            "save-test",
            {"save_folder": str(tmp_path), "save_file_name": "result.dat"},
        )

    assert target.read_text(encoding="utf-8") == "old result\n"
    assert set(tmp_path.iterdir()) == before


def test_save_result_replace_failure_preserves_old_target_and_cleans_temp(
    tmp_path, monkeypatch
):
    service = _service_with_result()
    target = tmp_path / "result.dat"
    target.write_text("old result\n", encoding="utf-8")
    before = set(tmp_path.iterdir())
    real_replace = treatment_service_module.os.replace

    def fail_replace(source, destination):
        assert Path(destination) == target
        raise OSError("simulated replace failure")

    monkeypatch.setattr(treatment_service_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        service.save_result(
            "save-test",
            {"save_folder": str(tmp_path), "save_file_name": "result.dat"},
        )
    monkeypatch.setattr(treatment_service_module.os, "replace", real_replace)

    assert target.read_text(encoding="utf-8") == "old result\n"
    assert set(tmp_path.iterdir()) == before


def test_save_result_smb_uses_atomic_copier(monkeypatch):
    service = _service_with_result()
    calls = []

    monkeypatch.setattr(treatment_service_module, "is_smb_path", lambda path: True)
    monkeypatch.setattr(
        treatment_service_module, "smb_join", lambda folder, name: f"{folder}/{name}"
    )
    monkeypatch.setattr(
        treatment_service_module,
        "copy_local_file_to_smb",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("non-atomic SMB copier must not be used")
        ),
        raising=False,
    )

    def atomic_copy(local_path, save_path):
        calls.append((Path(local_path), save_path))
        return 42

    monkeypatch.setattr(
        treatment_service_module, "copy_local_file_to_smb_atomic", atomic_copy
    )

    saved = service.save_result(
        "save-test",
        {"save_folder": "smb://server/share", "save_file_name": "result.dat"},
    )

    assert saved["save_path"] == "smb://server/share/result.dat"
    assert saved["bytes"] == 42
    assert len(calls) == 1
    assert not calls[0][0].exists()


def _queue_recipe(tmp_path, *, fail_calc=False):
    source = tmp_path / "source.his"
    source.write_text("source", encoding="utf-8")
    return {
        "session": {
            "paths": {"ABS": str(source)},
            "path_sources": {"ABS": str(source)},
            "active_data_type": "ABS",
            "save_folder": str(tmp_path),
            "save_file_name": "result.dat",
        },
        "inputs": {"ABS": {"path": str(source), "source_path": str(source)}},
        "convert_to_h5": {"ABS": True},
        "cleaning": {
            "state": "pending",
            "data_types": ["ABS"],
            "angle_threshold": 1.0,
            "surface_threshold": 1.0,
        },
        "output": {
            "path": str(tmp_path / "result.dat"),
            "save_folder": str(tmp_path),
            "save_file_name": "result.dat",
        },
        "fail_calc": fail_calc,
    }, source


@pytest.mark.parametrize("fail_calc", [False, True])
def test_queue_execution_is_job_local_and_resets_runtime_on_success_or_failure(
    tmp_path, monkeypatch, fail_calc
):
    import treatment_api as treatment_api_module

    recipe, source = _queue_recipe(tmp_path, fail_calc=fail_calc)
    order = []
    assigned_paths = []
    reset_ids = []

    monkeypatch.setattr(
        treatment_api_module,
        "_queue_preflight",
        lambda _recipe: order.append("preflight"),
    )

    def convert(_job_state, _data_type, _job_id):
        order.append("convert")
        output = tmp_path / "converted.h5"
        output.write_text("h5", encoding="utf-8")
        return {"output_path": str(output)}

    monkeypatch.setattr(treatment_api_module, "_queue_convert_to_job_h5", convert)

    def assign(job_state, data_type, output_path):
        assigned_paths.append((data_type, output_path))
        job_state.setdefault("paths", {})[data_type] = output_path

    monkeypatch.setattr(treatment_api_module, "_queue_assign_job_path", assign)

    service = treatment_api_module.treatment_service
    monkeypatch.setattr(
        service, "reset_runtime", lambda runtime_id=None: reset_ids.append(runtime_id)
    )
    monkeypatch.setattr(
        service,
        "save_sam_cleaned_h5",
        lambda *_args, **_kwargs: order.append("clean")
        or {"output_path": str(tmp_path / "cleaned.h5")},
    )

    def calc(runtime_id, _state):
        order.append("calc")
        if fail_calc:
            raise ValueError("calc failed")
        return {"od": runtime_id}

    monkeypatch.setattr(service, "calc_abs", calc)
    monkeypatch.setattr(
        service,
        "save_result",
        lambda runtime_id, _state: order.append("save") or {"save_path": "result.dat"},
    )

    if fail_calc:
        with pytest.raises(ValueError, match="calc failed"):
            treatment_api_module._execute_treatment_queue_job("job-fail", recipe)
    else:
        result = treatment_api_module._execute_treatment_queue_job("job-ok", recipe)
        assert result["saved"]["save_path"] == "result.dat"

    assert order == ["preflight", "convert", "clean", "calc"] + (
        [] if fail_calc else ["save"]
    )
    assert assigned_paths == [
        ("ABS", str(tmp_path / "converted.h5")),
        ("ABS", str(tmp_path / "cleaned.h5")),
    ]
    assert source.read_text(encoding="utf-8") == "source"
    assert reset_ids[-1] == f"queue:{'job-fail' if fail_calc else 'job-ok'}"
