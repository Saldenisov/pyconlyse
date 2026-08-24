"""Software-only contracts for read-only device discovery snapshots."""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace


BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from device_snapshot_service import DeviceSnapshotService


class FakeDatabase:
    def __init__(self, devices, infos=None):
        self.devices = list(devices)
        self.infos = dict(infos or {})

    def get_device_exported(self, _pattern):
        return list(self.devices)

    def get_device_info(self, device_name):
        value = self.infos.get(device_name)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise RuntimeError("missing device info")
        return value


class DeferredThread:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.created.append(self)

    def start(self):
        self.started = True


class StopMonitor(Exception):
    pass


class InlineThread:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def start(self):
        try:
            self.kwargs["target"](*self.kwargs.get("args", ()))
        except StopMonitor:
            pass


def test_snapshot_service_is_import_inert_and_has_no_web_or_tango_imports():
    source = (BACKEND / "device_snapshot_service.py").read_text(encoding="utf-8")
    imported_modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert imported_modules == {"threading", "time", "typing"}


def test_collect_filters_sorts_and_preserves_read_only_error_shape():
    infos = {
        "z/device": SimpleNamespace(ds_full_name="server/z", class_name="ZClass"),
        "a/device": RuntimeError("DB info unavailable"),
        "dserver/test": SimpleNamespace(ds_full_name="server/d", class_name="DClass"),
        "tango/admin/test": SimpleNamespace(ds_full_name="server/t", class_name="TClass"),
    }
    database = FakeDatabase(infos, infos)

    def read_device(device_name, server_name, dev_class):
        if device_name == "z/device":
            return "ON", server_name, dev_class
        if device_name == "a/device":
            raise RuntimeError("device offline")
        return "STANDBY", server_name, dev_class

    service = DeviceSnapshotService(lambda: database, read_device)
    devices = service.collect(probe_state=True, include_dserver=False, include_admin=False)

    assert devices == [
        {
            "name": "a/device",
            "state": "UNKNOWN",
            "server": None,
            "class": None,
            "available": False,
        },
        {
            "name": "z/device",
            "state": "ON",
            "server": "server/z",
            "class": "ZClass",
            "available": True,
        },
    ]
    all_devices = service.collect(probe_state=False, include_dserver=True, include_admin=True)
    assert [item["name"] for item in all_devices] == [
        "a/device",
        "dserver/test",
        "tango/admin/test",
        "z/device",
    ]
    assert all_devices[0]["available"] is True
    assert all_devices[0]["state"] == "UNKNOWN"


def test_snapshot_cache_is_keyed_fresh_and_stale_refresh_is_one_flight():
    now = [100.0]
    calls = []
    database = FakeDatabase(["device/test"])

    def collect_device(device_name, server_name, dev_class):
        calls.append(device_name)
        return "ON", server_name, dev_class

    DeferredThread.created.clear()
    service = DeviceSnapshotService(
        lambda: database,
        collect_device,
        clock=lambda: now[0],
        thread_factory=DeferredThread,
    )

    fresh = service.get_snapshot(True, True, False)
    cached = service.get_snapshot(True, True, False)
    keyed_separately = service.get_snapshot(False, True, False)

    assert fresh["cached"] is False
    assert cached["cached"] is True
    assert cached["snapshot_age_s"] == 0.0
    assert keyed_separately["cached"] is False
    assert calls == ["device/test"]

    now[0] = 106.0
    stale = service.get_snapshot(True, True, False, stale_ok=True, cache_ttl_s=4.0)
    stale_while_refreshing = service.get_snapshot(
        True,
        True,
        False,
        stale_ok=True,
        cache_ttl_s=4.0,
    )

    assert stale["cached"] is True
    assert stale["refreshing"] is False
    assert stale_while_refreshing["cached"] is True
    assert stale_while_refreshing["refreshing"] is True
    assert len(DeferredThread.created) == 1
    assert DeferredThread.created[0].started is True


def test_forced_or_expired_snapshot_reads_fresh_data():
    now = [10.0]
    database_calls = []

    def database_factory():
        database_calls.append(True)
        return FakeDatabase(["device/test"])

    service = DeviceSnapshotService(
        database_factory,
        lambda _name, server, dev_class: ("ON", server, dev_class),
        clock=lambda: now[0],
    )

    service.get_snapshot(False, True, False)
    service.get_snapshot(False, True, False, refresh=True)
    now[0] = 20.0
    service.get_snapshot(False, True, False, cache_ttl_s=4.0)

    assert len(database_calls) == 3


def test_monitor_is_one_shot_and_enforces_five_second_minimum_interval():
    scheduled = []
    sleeps = []

    def sleeper(interval):
        sleeps.append(interval)
        raise StopMonitor

    service = DeviceSnapshotService(
        lambda: FakeDatabase([]),
        lambda _name, server, dev_class: ("ON", server, dev_class),
        sleeper=sleeper,
        thread_factory=InlineThread,
    )
    service.schedule_refresh = lambda cache_key: scheduled.append(cache_key) or True

    assert service.start_monitor(interval_s=0.5) is True
    assert service.start_monitor(interval_s=10.0) is False
    assert scheduled == [(True, True, True)]
    assert sleeps == [5.0]
