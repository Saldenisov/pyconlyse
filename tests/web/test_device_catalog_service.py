"""Software-only contracts for class-based read-only device catalogs."""

import ast
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[2] / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from device_catalog_service import DeviceCatalogService


class FakeDatabase:
    def __init__(self, devices_by_class):
        self.devices_by_class = dict(devices_by_class)
        self.calls = []

    def get_device_name(self, pattern, class_name):
        self.calls.append((pattern, class_name))
        result = self.devices_by_class[class_name]
        if isinstance(result, Exception):
            raise result
        return result


def test_catalog_service_is_import_inert_without_tango_or_web_imports():
    source = (BACKEND / "device_catalog_service.py").read_text(encoding="utf-8")
    imported_modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    assert imported_modules == set()


def test_daq_catalog_keeps_class_order_failure_first_match_and_name_sort():
    database = FakeDatabase(
        {
            "First": ["z/device", "shared/device"],
            "Unavailable": RuntimeError("class offline"),
            "Third": ["a/device", "shared/device"],
        }
    )
    service = DeviceCatalogService()

    def read_state(device_name):
        if device_name == "a/device":
            raise RuntimeError("device offline")
        return "ON"

    devices = service.list_class_devices(
        database,
        ("First", "Unavailable", "Third"),
        probe_state=True,
        read_state=read_state,
        deduplicate=True,
    )

    assert database.calls == [
        ("*", "First"),
        ("*", "Unavailable"),
        ("*", "Third"),
    ]
    assert devices == [
        {"name": "a/device", "class": "Third", "state": "UNKNOWN", "available": False},
        {"name": "shared/device", "class": "First", "state": "ON", "available": True},
        {"name": "z/device", "class": "First", "state": "ON", "available": True},
    ]


def test_psp_catalog_retains_duplicates_and_uses_state_fallback():
    database = FakeDatabase({"DS_PSP": ["z/device", "a/device", "a/device"]})
    service = DeviceCatalogService()

    def read_state(device_name):
        if device_name == "z/device":
            raise RuntimeError("device offline")
        return "STANDBY"

    devices = service.list_class_devices(
        database,
        ("DS_PSP",),
        probe_state=True,
        read_state=read_state,
        deduplicate=False,
    )

    assert devices == [
        {"name": "a/device", "class": "DS_PSP", "state": "STANDBY", "available": True},
        {"name": "a/device", "class": "DS_PSP", "state": "STANDBY", "available": True},
        {"name": "z/device", "class": "DS_PSP", "state": "UNKNOWN", "available": False},
    ]


def test_catalog_without_state_probe_keeps_unknown_available_rows():
    database = FakeDatabase({"DS_PSP": ["device/test"]})
    service = DeviceCatalogService()

    devices = service.list_class_devices(
        database,
        ("DS_PSP",),
        probe_state=False,
        read_state=lambda _name: (_ for _ in ()).throw(AssertionError("not called")),
        deduplicate=False,
    )

    assert devices == [
        {"name": "device/test", "class": "DS_PSP", "state": "UNKNOWN", "available": True}
    ]
