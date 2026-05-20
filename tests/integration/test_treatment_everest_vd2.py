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
from treatment_network_path import is_smb_path, smb_isdir, smb_listdir
from treatment_api import session_store, treatment_api, treatment_service


DEFAULT_EVEREST_ROOT = "smb://10.20.30.202/e/DATA_VD2"
DEFAULT_EVEREST_HOST = "10.20.30.202"
DEFAULT_EVEREST_NETBIOS = "Everest"


def _everest_root_candidates():
    explicit_root = os.environ.get("PYCONLYSE_EVEREST_VD2_ROOT")
    if explicit_root:
        yield explicit_root

    system_name = platform.system().lower()
    if system_name == "windows":
        host = os.environ.get("PYCONLYSE_EVEREST_HOST", DEFAULT_EVEREST_HOST)
        netbios = os.environ.get("PYCONLYSE_EVEREST_NETBIOS", DEFAULT_EVEREST_NETBIOS)
        yield r"E:/DATA_VD2"
        yield r"E:/Data/DATA_VD2"
        yield rf"\\{netbios}\e\DATA_VD2"
        yield Path(rf"\\{netbios}\e\Data\DATA_VD2")
        yield Path(rf"\\{netbios}\E\Data\DATA_VD2")
        yield rf"\\{host}\e\DATA_VD2"
        yield Path(rf"\\{host}\E\Data\DATA_VD2")
        yield Path(rf"\\{host}\e\Data\DATA_VD2")
        yield Path(rf"\\{host}\Data\DATA_VD2")
        yield Path(rf"\\{host}\DATA_VD2")
        return

    yield DEFAULT_EVEREST_ROOT
    yield Path("/dev/DATA/VD2")
    yield Path("/Volumes/E/Data/DATA_VD2")
    yield Path("/Volumes/Data/DATA_VD2")
    yield Path("/Volumes/DATA_VD2")
    yield Path("/mnt/everest/Data/DATA_VD2")


def _everest_root() -> str:
    tried = []
    for candidate in _everest_root_candidates():
        tried.append(str(candidate))
        try:
            if is_smb_path(str(candidate)):
                if smb_isdir(str(candidate)):
                    return str(candidate)
            elif Path(candidate).is_dir():
                return str(candidate)
        except ValueError as exc:
            tried.append(str(exc))
    raise FileNotFoundError(
        "Everest VD2 root is not available. "
        f"Host is {os.environ.get('PYCONLYSE_EVEREST_HOST', DEFAULT_EVEREST_HOST)}. "
        "Set PYCONLYSE_SMB_USERNAME/PYCONLYSE_SMB_PASSWORD or mount SMB locally. "
        f"Tried: {tried}"
    )


def _find_abs_his(root: str) -> str:
    if is_smb_path(root):
        stack = [root]
        for _ in range(500):
            if not stack:
                break
            folder = stack.pop()
            for item in smb_listdir(folder):
                name = item["name"]
                if item["is_file"] and name.upper().startswith("ABS") and name.lower().endswith(".his"):
                    return str(item["path"])
                if item["is_dir"]:
                    stack.append(str(item["path"]))
        raise FileNotFoundError("No ABS*.his file found")

    for folder, _dirnames, filenames in os.walk(root):
        for filename in sorted(filenames):
            if filename.upper().startswith("ABS") and filename.lower().endswith(".his"):
                return str(Path(folder) / filename)
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
    if is_smb_path(root):
        monkeypatch.delenv("PYCONLYSE_TREATMENT_ROOT_BASE", raising=False)
    else:
        monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(Path(root).parent))
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
