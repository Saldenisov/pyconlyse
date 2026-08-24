"""Import-time Tango isolation contract for web/backend/routes.py."""

import importlib
import os
import sys
from pathlib import Path
import types

import pytest
from flask import Flask


BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"


class FakeTango:
    database_calls = 0
    proxy_calls = 0

    class Database:
        def __init__(self):
            FakeTango.database_calls += 1

    class DeviceProxy:
        def __init__(self, *_args, **_kwargs):
            FakeTango.proxy_calls += 1
            raise AssertionError("DeviceProxy must not be used during import")


def import_routes(monkeypatch, *, explicit_host=None):
    monkeypatch.syspath_prepend(str(BACKEND))
    monkeypatch.delenv("TANGO_HOST", raising=False)
    monkeypatch.delenv("PYCONLYSE_TANGO_HOST", raising=False)
    if explicit_host is not None:
        monkeypatch.setenv("PYCONLYSE_TANGO_HOST", explicit_host)
    FakeTango.database_calls = 0
    FakeTango.proxy_calls = 0
    monkeypatch.setitem(sys.modules, "tango", types.SimpleNamespace(
        Database=FakeTango.Database,
        DeviceProxy=FakeTango.DeviceProxy,
    ))
    sys.modules.pop("routes", None)
    return importlib.import_module("routes")


def test_import_is_offline_and_does_not_set_remote_default(monkeypatch):
    module = import_routes(monkeypatch)
    assert FakeTango.database_calls == 0
    assert FakeTango.proxy_calls == 0
    assert "TANGO_HOST" not in os.environ
    assert "PYCONLYSE_TANGO_HOST" not in os.environ
    assert module.db is None
    app_source = (BACKEND / "app.py").read_text(encoding="utf-8")
    assert "10.20.30.202:10000" not in app_source


def test_explicit_pyconlyse_tango_host_is_preserved_without_database(monkeypatch):
    import_routes(monkeypatch, explicit_host="fake-host:10000")
    assert os.environ["PYCONLYSE_TANGO_HOST"] == "fake-host:10000"
    assert os.environ["TANGO_HOST"] == "fake-host:10000"
    assert FakeTango.database_calls == 0


def test_database_lookup_is_lazy_and_only_explicit(monkeypatch):
    module = import_routes(monkeypatch)
    assert FakeTango.database_calls == 0
    module.check_tango_database()
    assert FakeTango.database_calls == 1


class DirectJiveDatabase:
    def __init__(self):
        FakeTango.database_calls += 1

    def get_class_list(self, _pattern):
        return ["server/test", "TestClass"]

    def get_server_list(self, _pattern):
        return ["server/test"]

    def get_device_class_list(self, _server):
        return ["device/test", "TestClass"]

    def get_device_exported(self, _pattern):
        return ["device/test"]

    def get_device_info(self, _device):
        return types.SimpleNamespace(
            class_name="TestClass",
            ds_full_name="server/test",
            host="stub.invalid",
            exported=True,
        )

    def get_device_property_list(self, _device, _pattern):
        return ["test_property"]

    def get_device_property(self, _device, property_name):
        return {property_name: ["value"]}


@pytest.mark.parametrize(
    ("path", "payload_key"),
    (
        ("/api/jive/classes", "classes"),
        ("/api/jive/servers", "servers"),
        ("/api/jive/devices", "devices"),
        ("/api/jive/device/device/test", "name"),
    ),
)
def test_jive_routes_lazily_create_database_without_tango_status(
    monkeypatch, path, payload_key
):
    module = import_routes(monkeypatch)
    module.tango = types.SimpleNamespace(
        Database=DirectJiveDatabase,
        DeviceProxy=FakeTango.DeviceProxy,
    )
    application = Flask(__name__)
    application.register_blueprint(module.routes)

    assert module.db is None
    assert FakeTango.database_calls == 0
    response = application.test_client().get(path)

    assert response.status_code == 200
    assert payload_key in response.get_json()
    assert FakeTango.database_calls == 1
