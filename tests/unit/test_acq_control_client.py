"""No network: reject old/unqualified command-capable XP releases."""
import copy
import pytest
from DeviceServers.control.elyse_acq.control_client import ControlClient
from tests.web.test_acq_control_api import view_fixture, request_command


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
