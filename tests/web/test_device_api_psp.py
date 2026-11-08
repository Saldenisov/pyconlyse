import importlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from flask import Flask


def _install_tango_stub():
    if "tango" in sys.modules:
        return

    tango = types.ModuleType("tango")

    class AttrWriteType:
        READ = 0
        READ_WRITE = 1

    tango.AttrWriteType = AttrWriteType
    tango.Database = lambda: None
    tango.DeviceProxy = lambda _name: None
    sys.modules["tango"] = tango


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "web" / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

_install_tango_stub()


class FakePSPDevice:
    def __init__(self):
        self.calls = []
        self.pending = [
            {"id": 1, "channel": "elyse/hf/attenuator/set", "value": 0.3, "status": "queued"},
            {"id": 2, "channel": "elyse/modulator/power/set", "value": 1.1, "status": "queued"},
        ]

    def state(self):
        return "ON"

    def get_command_list(self):
        return [
            "get_group_history_json",
            "get_history_json",
            "get_pending_commands_json",
            "pop_pending_commands_json",
            "acknowledge_command_json",
        ]

    def command_inout(self, name, arg=None):
        self.calls.append((name, arg))
        if str(name).lower() == "get_group_history_json":
            query = str(arg or "")
            group = query.split("|")[0] if "|" in query else query
            if group == "vacuum":
                payload = {
                    "history": [
                        {
                            "id": 11,
                            "payload": "elyse/vacuum/HF/measurement:-1.1e-08:1.0",
                            "group": "vacuum",
                            "channel": "elyse/vacuum/HF/measurement",
                            "value": -1.1e-08,
                            "source_ts": 1.0,
                            "recv_ts": 1.1,
                        },
                        {
                            "id": 12,
                            "payload": "elyse/vacuum/section/measurement:-4.6e-09:2.0",
                            "group": "vacuum",
                            "channel": "elyse/vacuum/section/measurement",
                            "value": -4.6e-09,
                            "source_ts": 2.0,
                            "recv_ts": 2.1,
                        },
                    ]
                }
            else:
                payload = {"history": []}
            return json.dumps(payload)

        if str(name).lower() == "get_history_json":
            return json.dumps([])
        if str(name).lower() == "get_pending_commands_json":
            limit = int(arg or 0)
            items = list(self.pending[-limit:]) if limit > 0 else list(self.pending)
            return json.dumps({"pending_count": len(self.pending), "items": items})
        if str(name).lower() == "pop_pending_commands_json":
            limit = int(arg or 1)
            popped = []
            for _ in range(min(limit, len(self.pending))):
                popped.append(self.pending.pop(0))
            return json.dumps({"pending_count": len(self.pending), "items": popped})
        if str(name).lower() == "acknowledge_command_json":
            payload = json.loads(str(arg or "{}"))
            return json.dumps({"success": True, "ack": payload})
        return json.dumps({})


class FakeDatabase:
    def get_device_name(self, _wildcard, class_name):
        if class_name == "DS_DAQmx":
            return ["control/DAQ/TRANCON-DAQ"]
        if class_name == "DS_PSP":
            return ["manip/general/PSP"]
        if class_name == "DS_DAQmx_ZMQ":
            return ["manip/general/DAQ"]
        return []


def _make_client(monkeypatch):
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    sys.modules.pop("device_api", None)
    device_api_module = importlib.import_module("device_api")
    import mutation_auth
    monkeypatch.setattr(mutation_auth, "mutation_auth_required", lambda: False)
    importlib.reload(device_api_module)
    # Legacy per-route JWT preprocessing is outside this PSP contract fixture.
    monkeypatch.setattr(device_api_module, "_maybe_require_auth", lambda: None)
    device_api_module.device_cache.clear()

    fake_device = FakePSPDevice()
    fake_db = FakeDatabase()

    monkeypatch.setattr(device_api_module.tango_gateway, "create_database", lambda: fake_db)
    monkeypatch.setattr(device_api_module.DeviceManager, "get_device", lambda _name: fake_device)

    app = Flask(__name__)
    app.register_blueprint(device_api_module.device_api)
    return app.test_client(), fake_device


def test_list_psp_devices(monkeypatch):
    client, _ = _make_client(monkeypatch)
    response = client.get("/api/psp/devices")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["devices"] == [
        {
            "available": True,
            "class": "DS_PSP",
            "name": "manip/general/PSP",
            "state": "ON",
        }
    ]


def test_list_daqmx_devices_defaults_to_state_probe_and_preserves_payload(monkeypatch):
    client, _ = _make_client(monkeypatch)
    response = client.get("/api/daqmx/devices")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "devices": [
            {
                "available": True,
                "class": "DS_DAQmx",
                "name": "control/DAQ/TRANCON-DAQ",
                "state": "ON",
            },
            {
                "available": True,
                "class": "DS_DAQmx_ZMQ",
                "name": "manip/general/DAQ",
                "state": "ON",
            },
            {
                "available": True,
                "class": "DS_PSP",
                "name": "manip/general/PSP",
                "state": "ON",
            },
        ],
        "success": True,
    }


class FakeDirectDAQmxDevice:
    def __init__(self):
        self.calls = []
        self.latest = {
            "timestamp": 10.5,
            "source": "direct",
            "device": "TRANCON-DAQ",
            "data": {
                "Laser_SC Shutter": {
                    "name": "Laser_SC Shutter",
                    "channel": "TRANCON-DAQ/port0/line0",
                    "kind": "DigitalOut",
                    "value": -1,
                    "value_known": False,
                    "alarm": False,
                    "unit": "",
                },
                "Power Status": {
                    "name": "Power Status",
                    "channel": "TRANCON-DAQ/ai0",
                    "kind": "AIcurrent",
                    "value": 120.0,
                    "raw_value": 0.00012,
                    "value_known": True,
                    "alarm": False,
                    "unit": "uA",
                    "multiplier": 1000000,
                    "limit_alarm_min": 100,
                    "limit_alarm_max": 1000,
                },
            },
        }

    def state(self):
        return "ON"

    def get_command_list(self):
        return ["get_latest_values_json", "write_digital_output", "reset_counter"]

    def command_inout(self, name, arg=None):
        self.calls.append((name, arg))
        if str(name).lower() == "get_latest_values_json":
            return json.dumps(self.latest)
        if str(name).lower() == "write_digital_output":
            return json.dumps({"name": arg[0], "value": int(arg[1])})
        if str(name).lower() == "reset_counter":
            return f"OK: reset {arg}"
        raise ValueError(name)

    def read_attribute(self, name):
        if str(name).lower() == "device_info_json":
            return SimpleNamespace(value=json.dumps({
                "name": "TRANCON-DAQ",
                "product_type": "PCIe-6320",
                "serial_num": 29471170,
            }))
        raise KeyError(name)


def test_direct_daqmx_snapshot_and_commands(monkeypatch):
    client, _ = _make_client(monkeypatch)
    import device_api

    direct = FakeDirectDAQmxDevice()
    monkeypatch.setattr(device_api.DeviceManager, "get_device", lambda _name: direct)

    latest = client.get("/api/daqmx/device/control%2FDAQ%2FTRANCON-DAQ/latest")
    payload = latest.get_json()
    assert latest.status_code == 200
    assert payload["device_info"]["product_type"] == "PCIe-6320"
    assert payload["channels"] == [
        {
            "alarm": False,
            "counter": "",
            "kind": "DigitalOut",
            "limit_alarm_max": None,
            "limit_alarm_min": None,
            "multiplier": 1.0,
            "name": "Laser_SC Shutter",
            "physical_channel": "TRANCON-DAQ/port0/line0",
            "raw_value": None,
            "unit": "",
            "value": -1,
            "value_known": False,
            "writable": True,
        },
        {
            "alarm": False,
            "counter": "",
            "kind": "AIcurrent",
            "limit_alarm_max": 1000,
            "limit_alarm_min": 100,
            "multiplier": 1000000,
            "name": "Power Status",
            "physical_channel": "TRANCON-DAQ/ai0",
            "raw_value": 0.00012,
            "unit": "uA",
            "value": 120.0,
            "value_known": True,
            "writable": False,
        },
    ]

    write = client.post(
        "/api/daqmx/device/control%2FDAQ%2FTRANCON-DAQ/write",
        json={
            "channel": "Laser_SC Shutter",
            "value": 1,
            "command_variant": "write_digital_output",
        },
    )
    assert write.status_code == 200
    assert ("write_digital_output", ["Laser_SC Shutter", "1"]) in direct.calls

    reset = client.post(
        "/api/daqmx/device/control%2FDAQ%2FTRANCON-DAQ/counter/reset",
        json={"channel": "ELYSE Pulse Counter", "command_variant": "reset_counter"},
    )
    assert reset.status_code == 200
    assert ("reset_counter", "ELYSE Pulse Counter") in direct.calls


def test_get_vacuum_group_history(monkeypatch):
    client, fake_device = _make_client(monkeypatch)
    response = client.get(
        "/api/psp/device/manip%2Fgeneral%2FPSP/group/vacuum/history?seconds=1800&limit=5000"
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["group"] == "vacuum"
    assert payload["sample_count"] == 2
    assert payload["channel_count"] == 2
    assert "elyse/vacuum/HF/measurement" in payload["series"]
    assert payload["latest_by_channel"]["elyse/vacuum/HF/measurement"]["value"] == -1.1e-08

    assert fake_device.calls
    assert fake_device.calls[0][0].lower() == "get_group_history_json"


def test_pending_commands_and_ack(monkeypatch):
    client, fake_device = _make_client(monkeypatch)

    pending = client.get(
        "/api/psp/device/manip%2Fgeneral%2FPSP/commands/pending?limit=1&pop=0"
    )
    pending_payload = pending.get_json()
    assert pending.status_code == 200
    assert pending_payload["success"] is True
    assert pending_payload["pending_count"] == 2
    assert len(pending_payload["items"]) == 1

    popped = client.get(
        "/api/psp/device/manip%2Fgeneral%2FPSP/commands/pending?limit=1&pop=1"
    )
    assert popped.status_code == 400
    assert len(fake_device.pending) == 2

    ack = client.post(
        "/api/psp/device/manip%2Fgeneral%2FPSP/commands/ack",
        json={"id": 1, "ok": True, "message": "done"},
    )
    ack_payload = ack.get_json()
    assert ack.status_code == 200
    assert ack_payload["success"] is True
    assert ack_payload["ack"]["id"] == 1

    assert len(fake_device.pending) == 2


def test_psp_ack_requires_strict_server_derived_authorization(monkeypatch):
    client, fake_device = _make_client(monkeypatch)
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "true")
    response = client.post(
        "/api/psp/device/manip%2Fgeneral%2FPSP/commands/ack",
        json={"id": 1, "ok": True, "role": "admin", "subject": "mallory"},
    )
    assert response.status_code == 409
    assert fake_device.calls == []
