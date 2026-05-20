import os
import platform
import sys
from pathlib import Path

import pytest
from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from folder_api import folder_api
from treatment_api import session_store, treatment_api, treatment_service


DEFAULT_EVEREST_ROOT = "E:/Data/DATA_VD2"
DEFAULT_EVEREST_HOST = "10.20.30.202"


def _everest_root_candidates():
    explicit_root = os.environ.get("PYCONLYSE_EVEREST_VD2_ROOT")
    if explicit_root:
        yield Path(explicit_root)

    system_name = platform.system().lower()
    if system_name == "windows":
        host = os.environ.get("PYCONLYSE_EVEREST_HOST", DEFAULT_EVEREST_HOST)
        yield Path(DEFAULT_EVEREST_ROOT)
        yield Path(rf"\\{host}\E\Data\DATA_VD2")
        yield Path(rf"\\{host}\Data\DATA_VD2")
        yield Path(rf"\\{host}\DATA_VD2")
        return

    yield Path(DEFAULT_EVEREST_ROOT)
    yield Path("/dev/DATA/VD2")
    yield Path("/Volumes/E/Data/DATA_VD2")
    yield Path("/Volumes/Data/DATA_VD2")
    yield Path("/Volumes/DATA_VD2")
    yield Path("/mnt/everest/Data/DATA_VD2")


def _everest_root() -> Path:
    tried = []
    for candidate in _everest_root_candidates():
        tried.append(str(candidate))
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        "Everest VD2 root is not available as a local filesystem path. "
        f"Host is {os.environ.get('PYCONLYSE_EVEREST_HOST', DEFAULT_EVEREST_HOST)}. "
        "Mount its SMB share first or set PYCONLYSE_EVEREST_VD2_ROOT. "
        f"Tried: {tried}"
    )


def _find_abs_his(root: Path) -> Path:
    for folder, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            if filename.upper().startswith("ABS") and filename.lower().endswith(".his"):
                return Path(folder) / filename
    raise FileNotFoundError("No ABS*.his file found")


def test_everest_vd2_cache_and_calculate_absorption_his(tmp_path, monkeypatch):
    if os.environ.get("PYCONLYSE_RUN_EVEREST_TREATMENT_TESTS") != "1":
        pytest.skip("Set PYCONLYSE_RUN_EVEREST_TREATMENT_TESTS=1 to run everest data test")

    try:
        root = _everest_root()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    try:
        abs_his = _find_abs_his(root)
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(root))
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(root))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(root.parent))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_CACHE_LIMIT_BYTES", str(1024 * 1024 * 1024))

    session_store.reset()
    treatment_service.reset_runtime()
    app = Flask(__name__)
    app.register_blueprint(folder_api)
    app.register_blueprint(treatment_api)

    with app.test_client() as client:
        config_response = client.post(
            "/api/treatment/session/config",
            json={
                "exp_type": "HIS",
                "selected_data_type": "ABS+BASE+NOISE",
                "calc_mode": "averaged",
            },
        )
        assert config_response.status_code == 200

        cache_response = client.post(
            "/api/treatment/session/cache-path",
            json={"data_type": "ABS+BASE+NOISE", "file_path": str(abs_his)},
        )
        cache_payload = cache_response.get_json()
        assert cache_response.status_code == 200
        assert Path(cache_payload["cached_file"]["cached_path"]).is_file()
        assert cache_payload["session"]["ready_for_calc"] is True

        calc_response = client.post("/api/treatment/calc-abs")
        calc_payload = calc_response.get_json()

    assert calc_response.status_code == 200
    assert calc_payload["session"]["result_ready"] is True
    assert calc_payload["result"]["shape"][0] > 0
    assert calc_payload["result"]["shape"][1] > 0
    assert len(calc_payload["result"]["sample"]) > 0
