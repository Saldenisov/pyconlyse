"""Network-free contracts for the current easy-scpi iTest wrapper."""

import importlib
import math
import sys
import types

import pytest

MODULE_NAME = "DeviceServers.power.iTest.scpi_client"


@pytest.fixture
def scpi_module(monkeypatch):
    """Import the wrapper against a local fake; never create a TCP socket."""

    class FakeInstrument:
        instances = []
        next_connect_error = None

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.connected = False
            self.connect_error = type(self).next_connect_error
            self.disconnect_error = None
            self.write_error = None
            self.query_error = None
            self.writes = []
            self.queries = []
            self.responses = {}
            type(self).instances.append(self)

        def connect(self):
            if self.connect_error:
                raise self.connect_error
            self.connected = True

        def disconnect(self):
            if self.disconnect_error:
                raise self.disconnect_error
            self.connected = False

        def write(self, command):
            if self.write_error:
                raise self.write_error
            self.writes.append(command)

        def query(self, command):
            self.queries.append(command)
            response = self.responses.get(command, "")
            if isinstance(response, Exception):
                raise response
            if self.query_error:
                raise self.query_error
            return response

    easy_scpi = types.ModuleType("easy_scpi")
    easy_scpi.Instrument = FakeInstrument
    monkeypatch.setitem(sys.modules, "easy_scpi", easy_scpi)
    sys.modules.pop(MODULE_NAME, None)
    module = importlib.import_module(MODULE_NAME)

    yield module, FakeInstrument

    sys.modules.pop(MODULE_NAME, None)


def connected_client(scpi_module, **kwargs):
    module, fake_instrument = scpi_module
    client = module.ITestSCPI("127.0.0.1", **kwargs)
    client.connect()
    return module, client, fake_instrument.instances[-1]


def test_constructor_preserves_eol_contract(scpi_module):
    module, _ = scpi_module

    client = module.ITestSCPI("example.test", port=7654, timeout=1.25, eol="\r\n")

    assert (client._host, client._port, client._timeout_s, client._eol) == (
        "example.test",
        7654,
        1.25,
        "\r\n",
    )
    with pytest.raises(ValueError, match="Unsupported EOL"):
        module.ITestSCPI("example.test", eol="\t")


def test_connect_uses_easy_instrument_socket_contract(scpi_module):
    module, client, instrument = connected_client(
        scpi_module, port=5026, timeout=1.25, eol="\r"
    )

    assert instrument.kwargs == {
        "port": "TCPIP::127.0.0.1::5026::SOCKET",
        "port_match": False,
        "timeout": 1250,
        "read_termination": "\r",
        "write_termination": "\r",
    }
    assert instrument.connected is True
    client.connect()
    assert len(scpi_module[1].instances) == 1


def test_connect_close_and_transport_errors_are_wrapped(scpi_module):
    module, fake_instrument = scpi_module
    fake_instrument.next_connect_error = RuntimeError("unreachable")
    client = module.ITestSCPI("127.0.0.1")
    with pytest.raises(module.SCPIError, match="Failed to connect"):
        client.connect()

    fake_instrument.next_connect_error = None
    module, client, instrument = connected_client(scpi_module)
    instrument.write_error = RuntimeError("write broke")
    with pytest.raises(module.SCPIError, match="Write failed"):
        client.select_slot(1)

    instrument.write_error = None
    instrument.query_error = RuntimeError("query broke")
    with pytest.raises(module.SCPIError, match="Query failed"):
        client.measure_current(1)

    client.close()
    assert client._inst is None
    assert instrument.connected is False


def test_close_clears_instance_when_disconnect_fails(scpi_module):
    _, client, instrument = connected_client(scpi_module)
    instrument.disconnect_error = RuntimeError("disconnect broke")

    with pytest.raises(RuntimeError, match="disconnect broke"):
        client.close()

    assert client._inst is None


def test_slot_ordering_readback_fallback_and_output_contract(scpi_module):
    _, client, instrument = connected_client(scpi_module)
    instrument.responses.update(
        {
            "SOUR:CURR?": RuntimeError("unsupported"),
            "CURR?": "0.125,ignored",
            "OUTP?": "ON",
            "INST:LIST?": "5,2811;1,2819;bad;3,2819",
        }
    )

    client.set_current(3, 0.125)
    assert instrument.writes == ["I 3", "CURR 0.1250"]
    assert client.get_current_setpoint(3) == 0.125
    assert instrument.writes[-1] == "I 3"
    assert client.get_output_state(3) == 1
    client.output_off(3)
    assert instrument.writes[-2:] == ["I 3", "OUTP OFF"]
    assert client.list_slots() == [(1, "2819"), (3, "2819"), (5, "2811")]


def test_batch_helpers_keep_requested_order_and_fail_safe(scpi_module):
    _, client, instrument = connected_client(scpi_module)
    current_responses = iter(["0.30", RuntimeError("slot failure"), "0.10"])
    state_responses = iter(["1", RuntimeError("slot failure"), "0"])

    def query(command):
        instrument.queries.append(command)
        if command == "MEAS:CURR?":
            response = next(current_responses)
        elif command == "OUTP?":
            response = next(state_responses)
        else:
            response = ""
        if isinstance(response, Exception):
            raise response
        return response

    instrument.query = query

    currents = client.measure_all_currents([3, 2, 1])
    states = client.read_all_states([3, 2, 1])

    assert currents[0] == 0.30
    assert math.isnan(currents[1])
    assert currents[2] == 0.10
    assert states == [1, 0, 0]
    assert instrument.writes == ["I 3", "I 2", "I 1", "I 3", "I 2", "I 1"]
