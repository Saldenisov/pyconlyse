"""Software-only contracts for the lazy Tango construction gateway."""

import importlib
import sys
import types
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"


class FakeTango:
    database_calls = 0
    proxy_calls = []

    class DevState:
        ON = object()
        MOVING = object()
        STANDBY = object()
        FAULT = object()

    class Database:
        def __init__(self):
            FakeTango.database_calls += 1

    class DeviceProxy:
        def __init__(self, device_name):
            FakeTango.proxy_calls.append(device_name)


def import_gateway(monkeypatch):
    monkeypatch.syspath_prepend(str(BACKEND))
    FakeTango.database_calls = 0
    FakeTango.proxy_calls = []
    monkeypatch.setitem(
        sys.modules,
        "tango",
        types.SimpleNamespace(
            Database=FakeTango.Database,
            DeviceProxy=FakeTango.DeviceProxy,
            DevState=FakeTango.DevState,
        ),
    )
    sys.modules.pop("tango_gateway", None)
    return importlib.import_module("tango_gateway")


def test_gateway_import_does_not_construct_tango_clients(monkeypatch):
    import_gateway(monkeypatch)

    assert FakeTango.database_calls == 0
    assert FakeTango.proxy_calls == []


def test_gateway_constructs_clients_only_on_factory_demand(monkeypatch):
    gateway = import_gateway(monkeypatch)

    database = gateway.create_database()
    proxy = gateway.create_device_proxy("test/device")

    assert isinstance(database, FakeTango.Database)
    assert isinstance(proxy, FakeTango.DeviceProxy)
    assert FakeTango.database_calls == 1
    assert FakeTango.proxy_calls == ["test/device"]


def test_gateway_preserves_starter_healthy_state_semantics(monkeypatch):
    gateway = import_gateway(monkeypatch)

    assert gateway.is_healthy_state(FakeTango.DevState.ON) is True
    assert gateway.is_healthy_state(FakeTango.DevState.MOVING) is True
    assert gateway.is_healthy_state(FakeTango.DevState.STANDBY) is True
    assert gateway.is_healthy_state(FakeTango.DevState.FAULT) is False
