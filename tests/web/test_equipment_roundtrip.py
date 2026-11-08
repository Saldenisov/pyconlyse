"""Software-only equipment lifecycle/transport integration with real Flask clients.

The simulated Init command models a ready device, not physical activation. These
tests never power outputs, move motors, or prove live hardware is connected.
"""

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask

from tests.web.test_device_api_smoke import FakeDatabase, FakeDevice


EQUIPMENT = (
    ("pdu/netio/1", "DS_Netio_pdu"),
    ("power/itest/1", "DS_itest_psu"),
    ("motion/standa/1", "DS_STANDA"),
    ("motion/owis/1", "DS_OWIS"),
    ("camera/basler/1", "DS_Basler_camera"),
    ("camera/andor/1", "DS_Andor_camera"),
    ("spectroscopy/avantes/1", "DS_Avantes"),
    ("control/daqmx/1", "DS_DAQmx"),
    ("control/vacuum/1", "DS_PSP"),
    ("control/laserpointing/1", "DS_LaserPointing"),
    ("electronics/keysight/1", "DS_Keysight"),
    ("electronics/dg645/1", "DS_DG645"),
)


class SimulatedEquipment(FakeDevice):
    def __init__(self, name, device_class):
        super().__init__(
            name,
            state="STANDBY",
            attributes={
                "hardware_connection_state": "CONNECTED",
                "initialization_state": "NOT_REQUESTED",
                "last_value": 0,
            },
        )
        self.device_class = device_class
        self.offline = False
        self.init_error = False

    def state(self):
        if self.offline:
            raise RuntimeError("simulated equipment disconnected")
        return super().state()

    def info(self):
        return SimpleNamespace(dev_class=self.device_class, server_id="simulated/1")

    def get_command_list(self):
        return ["Init", "Echo"]

    def command_inout(self, command_name, args=None):
        self.state()  # A disconnected device cannot accept a command.
        self.command_calls.append((command_name, args))
        if command_name == "Init":
            if self.init_error:
                self._state = "FAULT"
                self.attributes["initialization_state"] = "FAILED"
                raise RuntimeError("simulated initialization failed")
            self._state = "ON"
            self.attributes.update(
                hardware_connection_state="READY", initialization_state="SUCCEEDED"
            )
            return None
        if command_name != "Echo":
            raise ValueError("unsupported simulated command")
        if self._state != "ON":
            raise RuntimeError("equipment is not initialized")
        self.attributes["last_value"] = args
        return args


@pytest.fixture
def equipment_web(monkeypatch):
    monkeypatch.setenv("TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_TANGO_HOST", "stub.invalid:1")
    monkeypatch.setenv("PYCONLYSE_PRODUCTION", "false")
    monkeypatch.setenv("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    backend = str(Path(__file__).resolve().parents[2] / "web" / "backend")
    monkeypatch.syspath_prepend(backend)
    for name in ("device_api", "websocket_handler"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    api = importlib.import_module("device_api")
    ws = importlib.import_module("websocket_handler")
    devices = {name: SimulatedEquipment(name, cls) for name, cls in EQUIPMENT}
    database = FakeDatabase(devices, {})

    def proxy(name):
        return devices[str(name).replace("tango://stub.invalid:1/", "")]

    monkeypatch.setattr(api.tango_gateway, "create_device_proxy", proxy)
    monkeypatch.setattr(api.tango_gateway, "create_database", lambda: database)
    monkeypatch.setattr(ws, "_record_websocket_mutation", lambda **_event: None)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="software-only-test")
    app.register_blueprint(api.device_api)
    socket = ws.init_socketio(app)
    clients = []

    def connect():
        client = socket.test_client(app)
        assert client.is_connected()
        client.get_received()  # Clear connection acknowledgment.
        clients.append(client)
        return client

    yield SimpleNamespace(http=app.test_client(), connect=connect, devices=devices)
    for client in clients:
        if client.is_connected():
            client.disconnect()


def test_startup_discovers_every_equipment_without_activating_outputs(equipment_web):
    response = equipment_web.http.get("/api/devices?refresh=true&probe_state=true")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert {item["name"] for item in payload["devices"]} == set(equipment_web.devices)
    assert all(item["available"] for item in payload["devices"])
    assert all(item["state"] == "STANDBY" for item in payload["devices"])
    assert all(not device.command_calls for device in equipment_web.devices.values())


@pytest.mark.parametrize(
    "name,device_class", EQUIPMENT, ids=[cls for _, cls in EQUIPMENT]
)
@pytest.mark.parametrize("init_transport", ("http", "websocket"))
def test_init_then_http_command_and_websocket_reply(
    equipment_web, name, device_class, init_transport
):
    web = equipment_web
    client = web.connect()
    other_client = web.connect()
    base = f"/api/device/{name}"
    if init_transport == "http":
        response = web.http.post(f"{base}/command/Init", json={})
        assert response.status_code == 200
        assert response.get_json()["success"] is True
    else:
        client.emit("execute_command", {"device": name, "command": "Init"})
        [reply] = client.get_received()
        assert reply["name"] == "command_result"
        assert reply["args"][0]["success"] is True
    state = web.http.get(f"{base}/state").get_json()
    assert state["success"] is True
    assert state["state"] == "ON"
    attrs = web.http.get(f"{base}/attributes").get_json()["attributes"]
    assert attrs["hardware_connection_state"]["value"] == "READY"
    assert attrs["initialization_state"]["value"] == "SUCCEEDED"

    response = web.http.post(f"{base}/command/Echo", json={"args": [1, 2.5]})
    assert response.status_code == 200
    assert response.get_json()["result"] == [1, 2.5]
    assert web.http.get(f"{base}/attribute/last_value").get_json()["value"] == [1, 2.5]

    client.emit(
        "execute_command", {"device": name, "command": "Echo", "args": "acknowledged"}
    )
    [reply] = client.get_received()
    assert reply["name"] == "command_result"
    assert reply["args"][0]["success"] is True
    assert reply["args"][0]["result"] == "acknowledged"
    assert reply["args"][0]["device"] == name
    assert web.devices[name].command_calls == [
        ("Init", None),
        ("Echo", [1, 2.5]),
        ("Echo", "acknowledged"),
    ]

    # Immediate status must work without subscribing and remain private.
    client.emit("get_device_status", {"device": name})
    [update] = client.get_received()
    assert update["name"] == "device_update"
    assert update["args"][0]["device"] == name
    assert update["args"][0]["state"] == "ON"
    assert other_client.get_received() == []


def test_failed_init_and_disconnection_are_not_reported_as_ready(equipment_web):
    web = equipment_web
    name = EQUIPMENT[0][0]
    web.devices[name].init_error = True
    response = web.http.post(f"/api/device/{name}/command/Init", json={})
    assert response.status_code == 500
    assert response.get_json()["success"] is False
    assert web.http.get(f"/api/device/{name}/state").get_json()["state"] == "FAULT"
    web.devices[name].offline = True
    client = web.connect()
    client.emit("execute_command", {"device": name, "command": "Echo", "args": 1})
    [reply] = client.get_received()
    assert reply["name"] == "command_error"
    assert reply["args"][0]["success"] is False
    client.emit("get_device_status", {"device": name})
    [reply] = client.get_received()
    assert reply["name"] == "device_error"
    assert reply["args"][0]["connected"] is False
    response = web.http.get("/api/devices?refresh=true&probe_state=true")
    devices = {item["name"]: item for item in response.get_json()["devices"]}
    assert devices[name]["available"] is False
    assert all(devices[other]["available"] for other in web.devices if other != name)


def test_command_before_init_returns_failure_and_server_remains_usable(equipment_web):
    web = equipment_web
    name = EQUIPMENT[-1][0]
    base = f"/api/device/{name}"
    response = web.http.post(f"{base}/command/Echo", json={"args": 42})
    assert response.status_code == 500
    assert response.get_json()["success"] is False
    assert "not initialized" in response.get_json()["error"]
    assert web.http.get(f"{base}/state").get_json()["state"] == "STANDBY"
    assert web.http.post(f"{base}/command/Init", json={}).status_code == 200
    response = web.http.post(f"{base}/command/Echo", json={"args": 42})
    assert response.status_code == 200
    assert response.get_json()["result"] == 42
