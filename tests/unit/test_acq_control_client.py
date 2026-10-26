"""No network: reject old/unqualified command-capable XP releases."""
import copy
import pytest
from DeviceServers.control.elyse_acq.control_client import ControlClient, ControlBridge
from tests.web.test_acq_control_api import view_fixture, request_command
from tests.unit.test_acq_fault_telemetry import diagnostic_state
from legacy.xp_acq_control.elyse_agent.application_view import ApplicationView


@pytest.mark.parametrize("change", ["policy", "capabilities", "operation", "legacy", "initialization"])
def test_old_or_incompatible_runtime_is_not_commanded(change):
    value = view_fixture()["runtime"]
    if change == "policy": value["control_policy_version"] = 1
    if change == "capabilities": value["control"].pop("capabilities")
    if change == "operation": value["control"]["capabilities"]["arbitrary.write"] = dict(enabled=True, reason="")
    if change == "legacy": value["server_variant"] = "old_read_only_server"
    if change == "initialization": value["remote_initialization_enabled"] = True
    client = ControlClient(b"r" * 32, b"w" * 32, enabled=True)
    calls = []
    def exchange(path, body=None):
        calls.append(path)
        return copy.deepcopy(value)
    client._exchange = exchange
    with pytest.raises(ValueError): client.submit(request_command())
    assert calls == ["/snapshot"]


def test_disabled_facade_cannot_send_a_command():
    client = ControlClient(b"r" * 32, enabled=False)
    client._exchange = lambda *args: pytest.fail("network access from disabled client")
    with pytest.raises(RuntimeError, match="TANGO_COMMANDS_DISABLED"):
        client.submit(request_command())


def fault_bridge():
    value = diagnostic_state()
    value["latest"]["banks"]["C11_NI6220_AI"] = dict(
        kind="analog_input", device=11, values=[0.] * 16)
    value.update(build_id="c" * 64, control=dict(enabled=False))
    class Client:
        enabled = True
        def read(self):
            return copy.deepcopy(value)
    now = [10.]
    bridge = ControlBridge(Client(), clock=lambda: now[0])
    bridge.poll_once()
    return bridge, value, now


def test_fault_readback_retained_but_fault_and_disabled_controls_preserved():
    bridge, value, now = fault_bridge()
    result = bridge.snapshot()
    assert result["quality"] == "FAULT" and not result["source_current"]
    assert result["diagnostic_source_current"] and not result["measurements_hidden"]
    assert not result["commands_enabled"]
    assert result["runtime"]["latest"] == value["latest"]
    assert result["runtime"]["error"] == value["error"]


def test_fault_readback_expiry_hides_values_without_freshness_revival():
    bridge, value, now = fault_bridge()
    now[0] += 1.8
    result = bridge.snapshot()
    assert not result["diagnostic_source_current"] and result["measurements_hidden"]
    assert result["runtime"]["latest"] is None and result["quality"] == "FAULT"


def test_actual_application_cache_to_control_bridge_retains_diagnostic_inputs():
    bridge, value, now = fault_bridge()
    class Runtime:
        def snapshot(self):
            return copy.deepcopy(value)
    cache = ApplicationView(Runtime(), clock=lambda: now[0])
    cache.capture_once()
    now[0] += .1
    bridge.client.read = cache.snapshot
    bridge.poll_once()
    assert bridge.snapshot()["diagnostic_source_current"] is True
    assert bridge.snapshot()["runtime"]["latest"] is not None


@pytest.mark.parametrize("mutation", ["shape", "uncertainty", "attestation"])
def test_bad_shape_or_uncertain_owner_hides_all_runtime_inputs(mutation):
    bridge, value, now = fault_bridge()
    if mutation == "shape":
        value["latest"]["banks"]["C11_NI6220_AI"]["values"] = []
    elif mutation == "uncertainty":
        value["native_isolation"]["ownership_uncertain"] = True
    else:
        value.pop("fault_diagnostic_measurement")
    bridge.poll_once()
    result = bridge.snapshot()
    assert not result["diagnostic_source_current"] and result["runtime"]["latest"] is None
