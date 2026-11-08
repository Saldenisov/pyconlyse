import importlib
from pathlib import Path


def test_local_startup_overrides_inherited_production_settings(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "web"))
    local = importlib.import_module("start_local")
    development = importlib.import_module("start_pyconlyse_server")
    environment = {
        "PYCONLYSE_PRODUCTION": "true",
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "true",
        "PYCONLYSE_WEB_HOST": "0.0.0.0",
        "PYCONLYSE_WEB_DEBUG": "true",
        "PYCONLYSE_TREATMENT_ROOT": str(tmp_path),
    }
    local.configure_local_environment(environment)
    development.configure_development_environment(environment)
    assert environment["PYCONLYSE_PRODUCTION"] == "false"
    assert environment["PYCONLYSE_ENFORCE_DEVICE_AUTH"] == "false"
    assert environment["PYCONLYSE_WEB_HOST"] == "0.0.0.0"
    assert environment["PYCONLYSE_WEB_DEBUG"] == "false"
    assert set(environment["PYCONLYSE_CORS_ORIGINS"].split(",")) == {
        "http://127.0.0.1:5000", "http://localhost:5000",
        "http://10.20.30.202:5000", "http://129.175.100.128:5000",
        "http://127.0.0.1:3000", "http://localhost:3000",
    }
