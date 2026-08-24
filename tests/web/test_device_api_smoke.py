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


class FakeAttribute:
    def __init__(self, value):
        self.value = value
        self.quality = "ATTR_VALID"
        self.time = SimpleNamespace(tv_sec=1710000000)


class FakeAttributeConfig:
    def __init__(self, writable=1, data_type="float", unit="", description=""):
        self.writable = writable
        self.data_type = data_type
        self.unit = unit
        self.description = description


class FakeCommandConfig:
    def __init__(self):
        self.in_type = "DevVar"
        self.out_type = "DevVar"
        self.in_type_desc = "input"
        self.out_type_desc = "output"


class FakeDevice:
    def __init__(self, name, state="ON", status="OK", attributes=None, attr_configs=None):
        self.name = name
        self._state = state
        self._status = status
        self.attributes = dict(attributes or {})
        self.attr_configs = dict(attr_configs or {})
        self.command_calls = []

    def state(self):
        return self._state

    def status(self):
        return self._status

    def info(self):
        return SimpleNamespace(dev_class="FakeDS", server_id="fake/server")

    def get_attribute_list(self):
        return list(self.attributes.keys())

    def read_attribute(self, attr_name):
        if attr_name not in self.attributes:
            raise KeyError(attr_name)
        return FakeAttribute(self.attributes[attr_name])

    def write_attribute(self, attr_name, value):
        self.attributes[attr_name] = value

    def get_attribute_config(self, attr_name):
        return self.attr_configs.get(attr_name, FakeAttributeConfig())

    def get_command_list(self):
        return [
            "set_channels_states",
            "move_axis_abs",
            "move_axis",
            "stop_axis",
            "stop_movement",
            "set_output_state",
            "set_current",
            "turn_on",
        ]

    def get_command_config(self, _command_name):
        return FakeCommandConfig()

    def command_inout(self, command_name, args=None):
        self.command_calls.append((command_name, args))

        if command_name == "set_channels_states":
            self.attributes["output_statuses"] = args
            return 0

        if command_name == "move_axis_abs":
            target = args[0] if isinstance(args, list) else args
            self.attributes["position"] = float(target)
            return 0

        if command_name in {"move_axis", "define_position_axis"}:
            if isinstance(args, list) and len(args) >= 2:
                axis = int(args[0])
                value = float(args[1])
                positions = self.attributes.get("positions_map", {1: 0.0, 2: 0.0})
                positions[axis] = value
                self.attributes["positions_map"] = positions
                self.attributes["positions"] = str(positions)
            return 0

        if command_name in {"stop_axis", "stop_movement"}:
            return 0

        if command_name == "turn_on":
            self._state = "ON"
            return 0

        if command_name == "set_output_state":
            slot_id = int(args[0])
            value = int(args[1])
            self._set_slot_state(slot_id, value)
            return 0

        if command_name == "set_current":
            slot_id = int(float(args[0]))
            value = float(args[1])
            self._set_slot_current(slot_id, value)
            return 0

        return 0

    def _set_slot_state(self, slot_id, value):
        ids = list(self.attributes.get("ids", []))
        if slot_id in ids:
            idx = ids.index(slot_id)
            states = list(self.attributes.get("states", []))
            if idx < len(states):
                states[idx] = value
                self.attributes["states"] = states

    def _set_slot_current(self, slot_id, value):
        ids = list(self.attributes.get("ids", []))
        if slot_id in ids:
            idx = ids.index(slot_id)
            currents = list(self.attributes.get("currents_setpoint", []))
            if idx < len(currents):
                currents[idx] = value
                self.attributes["currents_setpoint"] = currents


class FakeDatabase:
    def __init__(self, devices, properties):
        self.devices = devices
        self.properties = properties

    def get_device_exported(self, _pattern):
        return list(self.devices.keys())

    def get_device_property_list(self, device_name, _pattern):
        return list(self.properties.get(device_name, {}).keys())

    def get_device_property(self, device_name, prop_name):
        device_props = self.properties.get(device_name, {})
        return {prop_name: device_props.get(prop_name, [])}

    def get_device_info(self, device_name):
        device = self.devices[device_name]
        return SimpleNamespace(
            class_name=getattr(device.info(), "dev_class", "FakeDS"),
            ds_full_name=getattr(device.info(), "server_id", "fake/server"),
            server=getattr(device.info(), "server_id", "fake/server"),
        )


def _build_fake_backend():
    devices = {
        "pdu/netio/1": FakeDevice(
            "pdu/netio/1",
            attributes={"output_statuses": [1, 0, 1, 0], "name": "NETIO PDU"},
        ),
        "manip/v0/dv04": FakeDevice(
            "manip/v0/dv04",
            attributes={"position": 1.25},
            attr_configs={"position": FakeAttributeConfig(unit="mm")},
        ),
        "elyse/motorized/owis": FakeDevice(
            "elyse/motorized/owis",
            attributes={
                "positions": "{1: 0.0, 2: 1.0}",
                "states": "{1: 1, 2: 3}",
                "positions_map": {1: 0.0, 2: 1.0},
            },
        ),
        "power/itest/1": FakeDevice(
            "power/itest/1",
            attributes={
                "ids": [11, 12],
                "names": ["Slot 11", "Slot 12"],
                "states": [1, 0],
                "currents_setpoint": [0.5, 1.0],
                "currents_meas": [0.45, 0.95],
                "current_limits": [-1.0, 2.0, -1.0, 2.0],
                "voltages_meas": [5.0, 5.1],
            },
        ),
    }

    properties = {
        "manip/v0/dv04": {
            "unit": ["mm"],
            "limit_min": ["-10"],
            "limit_max": ["10"],
            "friendly_name": ["dv04"],
            "preset_pos": ["0", "5"],
        },
        "power/itest/1": {
            "tab_config": [
                json.dumps(
                    {
                        "VD": {"slots": [11], "defaults": {"11": 0.4}, "enabled": True},
                        "VD2": {"slots": [12], "defaults": {"12": 0.8}, "enabled": True},
                        "RF": {"slots": [], "defaults": {}, "enabled": True},
                        "ALL": {"slots": [11, 12], "defaults": {}, "enabled": True},
                    }
                )
            ]
        },
    }

    return devices, properties


def _make_client(monkeypatch):
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    sys.modules.pop("device_api", None)
    device_api_module = importlib.import_module("device_api")
    device_api_module.device_cache.clear()

    devices, properties = _build_fake_backend()
    fake_db = FakeDatabase(devices, properties)

    def fake_proxy(device_name):
        name = str(device_name)
        prefix = "tango://stub.invalid:1/"
        if name.startswith(prefix):
            name = name[len(prefix):]
        return devices[name]

    monkeypatch.setattr(
        device_api_module.tango,
        "DeviceProxy",
        fake_proxy,
        raising=False,
    )
    monkeypatch.setattr(
        device_api_module.tango,
        "Database",
        lambda: fake_db,
        raising=False,
    )

    app = Flask(__name__)
    app.register_blueprint(device_api_module.device_api)
    return app.test_client(), devices


def test_device_listing_and_standa_properties_smoke(monkeypatch):
    client, _devices = _make_client(monkeypatch)

    devices_response = client.get("/api/devices")
    devices_payload = devices_response.get_json()

    assert devices_response.status_code == 200
    assert devices_payload["success"] is True
    assert len(devices_payload["devices"]) == 4

    props_response = client.get("/api/device/manip/v0/dv04/properties")
    props_payload = props_response.get_json()

    assert props_response.status_code == 200
    assert props_payload["success"] is True
    assert props_payload["unit"] == ["mm"]
    assert props_payload["limit_min"] == ["-10"]


def test_generic_device_lazy_endpoints_smoke(monkeypatch):
    client, _devices = _make_client(monkeypatch)

    summary_response = client.get("/api/device/manip/v0/dv04/summary")
    summary_payload = summary_response.get_json()
    assert summary_response.status_code == 200
    assert summary_payload["success"] is True
    assert summary_payload["device_info"]["name"] == "manip/v0/dv04"
    assert summary_payload["device_info"]["state"] == "ON"

    info_response = client.get(
        "/api/device/manip/v0/dv04/info?include_properties=0&include_attributes=0&include_commands=0"
    )
    info_payload = info_response.get_json()
    assert info_response.status_code == 200
    assert info_payload["success"] is True
    assert "properties" not in info_payload["device_info"]
    assert "attributes" not in info_payload["device_info"]
    assert "commands" not in info_payload["device_info"]

    attrs_response = client.get("/api/device/manip/v0/dv04/attributes")
    attrs_payload = attrs_response.get_json()
    assert attrs_response.status_code == 200
    assert attrs_payload["success"] is True
    assert attrs_payload["attributes"]["position"]["writable"] is True
    assert attrs_payload["attributes"]["position"]["unit"] == "mm"

    commands_response = client.get("/api/device/manip/v0/dv04/commands")
    commands_payload = commands_response.get_json()
    assert commands_response.status_code == 200
    assert commands_payload["success"] is True
    assert "move_axis_abs" in commands_payload["commands"]


def test_netio_page_routes_smoke(monkeypatch):
    client, devices = _make_client(monkeypatch)

    pdu_response = client.get("/api/device/pdu/netio/1/pdu/outputs")
    pdu_payload = pdu_response.get_json()
    assert pdu_response.status_code == 200
    assert pdu_payload["success"] is True
    assert pdu_payload["outputs"][0]["id"] == 1
    assert pdu_payload["outputs"][0]["state"] == 1

    attrs_response = client.get("/api/device/pdu/netio/1/attributes")
    attrs_payload = attrs_response.get_json()

    assert attrs_response.status_code == 200
    assert attrs_payload["success"] is True
    assert attrs_payload["attributes"]["output_statuses"]["value"] == [1, 0, 1, 0]

    cmd_response = client.post(
        "/api/device/pdu/netio/1/command/set_channels_states",
        json={"args": [1, 1, 0, 0]},
    )
    cmd_payload = cmd_response.get_json()

    assert cmd_response.status_code == 200
    assert cmd_payload["success"] is True
    assert cmd_payload["verified_states"][:4] == [1, 1, 0, 0]
    assert devices["pdu/netio/1"].command_calls[-1][0] == "set_channels_states"


def test_netio_command_returns_409_on_readback_mismatch(monkeypatch):
    client, devices = _make_client(monkeypatch)
    netio = devices["pdu/netio/1"]

    def _no_apply(command_name, args=None):
        netio.command_calls.append((command_name, args))
        return 0

    netio.command_inout = _no_apply

    cmd_response = client.post(
        "/api/device/pdu/netio/1/command/set_channels_states",
        json={"args": [0, 0, 0, 0]},
    )
    cmd_payload = cmd_response.get_json()

    assert cmd_response.status_code == 409
    assert cmd_payload["success"] is False
    assert "readback states" in cmd_payload["error"]
    assert cmd_payload["requested_states"] == [0, 0, 0, 0]


def test_netio_output_fallback_does_not_hide_non_attribute_read_errors(monkeypatch):
    client, devices = _make_client(monkeypatch)
    netio = devices["pdu/netio/1"]
    original_read = netio.read_attribute
    reads = []

    def fail_states_only(attr_name):
        reads.append(attr_name)
        if attr_name == "states":
            raise RuntimeError("transport disconnected")
        return original_read(attr_name)

    netio.read_attribute = fail_states_only

    response = client.get("/api/device/pdu/netio/1/pdu/outputs")
    payload = response.get_json()

    assert response.status_code == 500
    assert payload["error"] == "transport disconnected"
    assert "output_statuses" not in reads


def test_standa_page_routes_smoke(monkeypatch):
    client, _devices = _make_client(monkeypatch)

    attr_response = client.get("/api/device/manip/v0/dv04/attribute/position")
    attr_payload = attr_response.get_json()
    assert attr_response.status_code == 200
    assert attr_payload["value"] == 1.25

    move_response = client.post(
        "/api/device/manip/v0/dv04/command/move_axis_abs",
        json={"args": [3.5]},
    )
    move_payload = move_response.get_json()
    assert move_response.status_code == 200
    assert move_payload["success"] is True

    verify_response = client.get("/api/device/manip/v0/dv04/attribute/position")
    verify_payload = verify_response.get_json()
    assert verify_payload["value"] == 3.5

    state_response = client.get("/api/device/manip/v0/dv04/state")
    state_payload = state_response.get_json()
    assert state_response.status_code == 200
    assert state_payload["state"] == "ON"


def test_owis_page_routes_smoke(monkeypatch):
    client, devices = _make_client(monkeypatch)

    attrs_response = client.get("/api/device/elyse/motorized/owis/attributes")
    attrs_payload = attrs_response.get_json()
    assert attrs_response.status_code == 200
    assert attrs_payload["success"] is True
    assert "positions" in attrs_payload["attributes"]

    move_response = client.post(
        "/api/device/elyse/motorized/owis/command/move_axis",
        json={"args": [1, 4.2]},
    )
    assert move_response.status_code == 200

    define_response = client.post(
        "/api/device/elyse/motorized/owis/command/define_position_axis",
        json={"args": [2, 6.5]},
    )
    assert define_response.status_code == 200
    assert devices["elyse/motorized/owis"].attributes["positions_map"][2] == 6.5

    stop_response = client.post(
        "/api/device/elyse/motorized/owis/command/stop_axis",
        json={"args": [1]},
    )
    stop_payload = stop_response.get_json()
    assert stop_response.status_code == 200
    assert stop_payload["success"] is True


def test_itest_page_routes_smoke(monkeypatch):
    client, _devices = _make_client(monkeypatch)

    ds_slots_response = client.get("/api/device/ds_itest_psu/power/itest/1/slots")
    ds_slots_payload = ds_slots_response.get_json()
    assert ds_slots_response.status_code == 200
    assert ds_slots_payload["success"] is True
    assert ds_slots_payload["slot_count"] == 2
    assert ds_slots_payload["slots"][0]["id"] == 11

    tab_config_response = client.get("/api/device/ds_itest_psu/power/itest/1/tab_config")
    tab_config_payload = tab_config_response.get_json()
    assert tab_config_response.status_code == 200
    assert tab_config_payload["success"] is True
    assert tab_config_payload["tab_configs"]["V0"]["slots"] == [11]
    assert tab_config_payload["tab_configs"]["REF"]["slots"] == []

    all_slots_response = client.get("/api/device/itest/power/itest/1/all_slots")
    all_slots_payload = all_slots_response.get_json()
    assert all_slots_response.status_code == 200
    assert all_slots_payload["success"] is True
    assert all_slots_payload["ids"] == [11, 12]

    output_response = client.post(
        "/api/device/itest/power/itest/1/slot/11/output",
        json={"state": 0},
    )
    output_payload = output_response.get_json()
    assert output_response.status_code == 200
    assert output_payload["success"] is True

    current_post_response = client.post(
        "/api/device/itest/power/itest/1/slot/11/current",
        json={"value": 1.2},
    )
    current_post_payload = current_post_response.get_json()
    assert current_post_response.status_code == 200
    assert current_post_payload["success"] is True

    current_get_response = client.get("/api/device/itest/power/itest/1/slot/11/current")
    current_get_payload = current_get_response.get_json()
    assert current_get_response.status_code == 200
    assert current_get_payload["success"] is True
    assert current_get_payload["slot_id"] == 11
    assert current_get_payload["current_setpoint"] == 1.2
