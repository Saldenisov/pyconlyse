import sys
from pathlib import Path

import pytest

NETIO_TEST_DIR = Path(__file__).resolve().parent
if str(NETIO_TEST_DIR) not in sys.path:
    sys.path.insert(0, str(NETIO_TEST_DIR))

from netio_test_support import netio_module


class DummyNetio(netio_module.DS_Netio_pdu):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self.locking_client_token = ""
        self.locked_client = False
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = netio_module.DevState.OFF
        self._name = "netio/test"
        self.device_id = "netio-1"
        self.friendly_name = "Netio"
        self.always_on = 0
        self.archive_enabled = 0
        self.ip_address = "10.0.0.5"
        self.authentication_name = "admin"
        self.authentication_password = "secret"
        self._device_id_internal = -1
        self._uri = ""
        self._status_check_fault = 0
        self._names = []
        self._ids = []
        self._states = []
        self._actions = []
        self._delays = []
        self.archive_payloads = []

    def write_to_archive(self, data):
        self.archive_payloads.append(data)


def _outputs_payload(*states):
    outputs = []
    for index, state in enumerate(states, start=1):
        outputs.append(
            {
                "ID": index,
                "Name": f"Output {index}",
                "State": state,
                "Action": state,
                "Delay": index * 10,
            }
        )
    return outputs


def _response(payload, status_code=200):
    return netio_module.requests.Response(status_code=status_code, payload=payload)


def test_addr_and_authentication_are_built_from_properties():
    device = DummyNetio()

    assert device._addr() == "http://10.0.0.5/netio.json"
    assert device._authentication() == ("admin", "secret")


def test_find_device_populates_identity_and_outputs_on_success():
    device = DummyNetio()
    payload = {
        "Agent": {"SerialNumber": "SN-123"},
        "Outputs": _outputs_payload(1, 0, 1, 0),
    }
    device._get_request = lambda: _response(payload)

    device.find_device()

    assert device._device_id_internal == 1
    assert device._uri == "SN-123"
    assert device._names == ["Output 1", "Output 2", "Output 3", "Output 4"]
    assert device._ids == [1, 2, 3, 4]
    assert device._states == [1, 0, 1, 0]
    assert device._actions == [1, 0, 1, 0]
    assert device._delays == [10, 20, 30, 40]
    assert len(device.archive_payloads) == 4


def test_find_device_keeps_missing_marker_when_request_fails():
    device = DummyNetio()
    device._get_request = lambda: False

    device.find_device()

    assert device._device_id_internal == -1
    assert device._uri == ""


def test_get_channels_state_local_updates_outputs_on_success():
    device = DummyNetio()
    device._get_request = lambda: _response({"Outputs": _outputs_payload(0, 1, 0, 1)})

    result = device.get_channels_state_local()

    assert result == 0
    assert device._states == [0, 1, 0, 1]


def test_get_channels_state_local_returns_message_on_failure():
    device = DummyNetio()
    device._get_request = lambda: False

    result = device.get_channels_state_local()

    assert "Could not get channels states" in result
    assert "Device netio-1 Netio" in result


def test_set_channels_states_local_builds_request_payload_and_updates_state():
    device = DummyNetio()
    device._ids = [1, 2, 3, 4]
    sent = {}

    def fake_send(payload):
        sent["payload"] = payload
        return _response({"Outputs": _outputs_payload(1, 1, 0, 0)})

    device._send_request = fake_send

    result = device.set_channels_states_local([1, 1, 0, 0])

    assert result == 0
    assert sent["payload"] == {
        "Outputs": [
            {"ID": 1, "Action": 1},
            {"ID": 2, "Action": 1},
            {"ID": 3, "Action": 0},
            {"ID": 4, "Action": 0},
        ]
    }
    assert device._states == [1, 1, 0, 0]


def test_set_channels_states_local_returns_fallback_message_on_send_failure():
    device = DummyNetio()
    device._ids = [1, 2]
    device._send_request = lambda payload: False

    result = device.set_channels_states_local([1, 0])

    assert result == "Unknown error during setting channels"


def test_get_request_returns_false_and_records_error_on_connection_error(monkeypatch):
    device = DummyNetio()

    def fake_get(*args, **kwargs):
        raise netio_module.requests.ConnectionError("offline")

    monkeypatch.setattr(netio_module.requests, "get", fake_get)

    result = device._get_request()

    assert result is False
    assert device.last_error() == "offline"


def test_requests_use_a_bounded_timeout(monkeypatch):
    device = DummyNetio()
    device.request_timeout_s = 1.25
    seen = {}

    def fake_get(*args, **kwargs):
        seen.update(kwargs)
        return _response({"Outputs": []})

    monkeypatch.setattr(netio_module.requests, "get", fake_get)

    device._get_request()

    assert seen["timeout"] == 1.25


def test_send_request_returns_false_and_records_error_on_request_exception(
    monkeypatch,
):
    device = DummyNetio()

    def fake_post(*args, **kwargs):
        raise netio_module.requests.RequestException("write failed")

    monkeypatch.setattr(netio_module.requests, "post", fake_post)

    result = device._send_request({"Outputs": []})

    assert result is False
    assert device.last_error() == "write failed"


def test_turn_on_local_retries_find_and_faults_when_device_is_missing():
    device = DummyNetio()
    find_calls = []

    def fake_find():
        find_calls.append(True)
        device._device_id_internal = -1
        device._uri = ""

    device.find_device = fake_find

    result = device.turn_on_local()

    assert len(find_calls) == 1
    assert "Device could not be found" in result
    assert device.get_state() == netio_module.DevState.FAULT


def test_turn_on_local_sets_on_when_device_is_present():
    device = DummyNetio()
    device._device_id_internal = 10

    result = device.turn_on_local()

    assert result == 0
    assert device.get_state() == netio_module.DevState.ON


def test_turn_off_local_sets_off_state():
    device = DummyNetio()
    device.set_state(netio_module.DevState.ON)

    result = device.turn_off_local()

    assert result == 0
    assert device.get_state() == netio_module.DevState.OFF


def test_register_variables_for_archive_adds_output_accessors():
    device = DummyNetio()
    device._states = [1, 0, 1, 0]

    device.register_variables_for_archive()

    assert "State" in device.archive_state
    assert "output1" in device.archive_state
    assert "output4" in device.archive_state
    assert device.archive_state["output1"][0]() == 1
    assert device.archive_state["output4"][0]() == 0


def test_get_channel_state_returns_selected_index():
    device = DummyNetio()
    device._states = [0, 1, 0, 1]

    assert device.get_channel_state(1) == 1
    assert device.get_channel_state(3) == 1


def test_get_controller_status_local_resets_fault_counter_on_success():
    device = DummyNetio()
    device._status_check_fault = 3
    device.set_state(netio_module.DevState.FAULT)
    device._get_request = lambda: _response({"Outputs": _outputs_payload(1, 1, 1, 1)})

    result = device.get_controller_status_local()

    assert result == 0
    assert device._status_check_fault == 0
    assert device._states == [1, 1, 1, 1]
    assert device.get_state() == netio_module.DevState.ON


def test_get_controller_status_local_faults_after_repeated_failures():
    device = DummyNetio()
    device._status_check_fault = 10
    device._get_request = lambda: False

    result = device.get_controller_status_local()

    assert "Could not get controller status" in result
    assert device._status_check_fault == 11
    assert device.get_state() == netio_module.DevState.FAULT


def test_get_controller_status_local_increments_counter_on_http_error():
    device = DummyNetio()
    device._status_check_fault = 0
    device._get_request = lambda: _response({"Outputs": []}, status_code=503)

    result = device.get_controller_status_local()

    assert "Could not get controller status" in result
    assert device._status_check_fault == 1
    assert device.get_state() == netio_module.DevState.OFF


def test_set_attributes_returns_exception_object_on_malformed_payload():
    device = DummyNetio()

    result = device._DS_Netio_pdu__set_attributes_netio([{"ID": 1}])

    assert isinstance(result, Exception)
    assert device._names == []
