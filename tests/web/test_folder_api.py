import sys
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from folder_api import (
    folder_api,
    get_allowed_root,
    get_default_allowed_root,
    get_treatment_root_base,
    set_allowed_root,
)


def _make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(tmp_path))
    app = Flask(__name__)
    app.register_blueprint(folder_api)
    return app.test_client()


def test_folder_contents_allows_paths_inside_root(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)
    nested = tmp_path / "run_001"
    nested.mkdir()
    (nested / "a.dat").write_text("ok", encoding="ascii")

    response = client.get("/api/folder-contents", query_string={"folder": str(nested)})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["path"] == str(nested)


def test_folder_contents_rejects_paths_outside_root(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)
    outside = tmp_path.parent

    response = client.get("/api/folder-contents", query_string={"folder": str(outside)})
    payload = response.get_json()

    assert response.status_code == 403
    assert payload["error"] == "Invalid folder"


def test_folder_contents_reports_missing_folder(tmp_path, monkeypatch):
    client = _make_client(tmp_path, monkeypatch)
    missing = tmp_path / "does-not-exist"

    response = client.get("/api/folder-contents", query_string={"folder": str(missing)})
    payload = response.get_json()

    assert response.status_code == 404
    assert payload["error"] == "Folder not found"


def test_default_allowed_root_follows_platform(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_TREATMENT_ROOT", raising=False)
    monkeypatch.delenv("PYCONLYSE_ALLOWED_ROOT", raising=False)

    monkeypatch.setattr("folder_api.platform.system", lambda: "Windows")
    assert get_default_allowed_root() == "E:/Data/DATA_VD2"
    assert get_allowed_root() == "E:/Data/DATA_VD2"

    monkeypatch.setattr("folder_api.platform.system", lambda: "Darwin")
    assert get_default_allowed_root() == "/dev/DATA/VD2"
    assert get_allowed_root() == "/dev/DATA/VD2"


def test_treatment_root_env_takes_precedence(tmp_path, monkeypatch):
    allowed_root = tmp_path / "allowed"
    treatment_root = tmp_path / "vd2"
    monkeypatch.setenv("PYCONLYSE_ALLOWED_ROOT", str(allowed_root))
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT", str(treatment_root))

    assert get_allowed_root() == str(treatment_root)


def test_treatment_root_base_limits_windows_and_everest(monkeypatch):
    monkeypatch.delenv("PYCONLYSE_TREATMENT_ROOT_BASE", raising=False)

    monkeypatch.setattr("folder_api.platform.system", lambda: "Windows")
    monkeypatch.setattr("folder_api.socket.gethostname", lambda: "anything")
    assert get_treatment_root_base() == "E:/"

    monkeypatch.setattr("folder_api.platform.system", lambda: "Linux")
    monkeypatch.setattr("folder_api.socket.gethostname", lambda: "everest")
    assert get_treatment_root_base() == "E:/"


def test_set_allowed_root_must_stay_inside_runtime_base(tmp_path, monkeypatch):
    root_base = tmp_path / "E"
    good_root = root_base / "VD2"
    outside_root = tmp_path / "outside"
    good_root.mkdir(parents=True)
    outside_root.mkdir()
    monkeypatch.delenv("PYCONLYSE_TREATMENT_ROOT", raising=False)
    monkeypatch.delenv("PYCONLYSE_ALLOWED_ROOT", raising=False)
    monkeypatch.setenv("PYCONLYSE_TREATMENT_ROOT_BASE", str(root_base))

    assert set_allowed_root(str(good_root)) == str(good_root)
    assert get_allowed_root() == str(good_root)

    try:
        set_allowed_root(str(outside_root))
    except ValueError as exc:
        assert "Treatment root must be inside" in str(exc)
    else:
        raise AssertionError("outside root should be rejected")
