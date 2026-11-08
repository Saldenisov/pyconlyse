import importlib
from pathlib import Path


def development_module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "web"))
    return importlib.import_module("start_pyconlyse_server")


def test_development_defaults_match_frontend_proxy(monkeypatch):
    module = development_module(monkeypatch)
    monkeypatch.setattr(module.Path, "is_dir", lambda _path: False)
    environment = {"PYCONLYSE_PRODUCTION": "true"}
    module.configure_development_environment(environment)
    assert environment["PYCONLYSE_PRODUCTION"] == "false"
    assert environment["PYCONLYSE_WEB_HOST"] == "127.0.0.1"
    assert environment["PYCONLYSE_WEB_PORT"] == "5000"
    assert environment["PYCONLYSE_ENFORCE_DEVICE_AUTH"] == "false"


def test_development_uses_existing_everest_data_root(monkeypatch):
    module = development_module(monkeypatch)
    monkeypatch.setattr(module.Path, "is_dir", lambda _path: True)
    environment = {}
    module.configure_development_environment(environment)
    assert environment["PYCONLYSE_TREATMENT_ROOT"] == "E:/DATA_VD2"


def test_explicit_development_settings_are_preserved(monkeypatch):
    module = development_module(monkeypatch)
    monkeypatch.setattr(module.Path, "is_dir", lambda _path: True)
    environment = {
        "PYCONLYSE_ALLOWED_ROOT": "C:/selected-data",
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_WEB_PORT": "5001",
    }
    module.configure_development_environment(environment)
    assert "PYCONLYSE_TREATMENT_ROOT" not in environment
    assert environment["PYCONLYSE_ENFORCE_DEVICE_AUTH"] == "true"
    assert environment["PYCONLYSE_WEB_PORT"] == "5001"
