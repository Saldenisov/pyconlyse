"""Owner-scoped facade/client/config tests; only RAM mocks and temp files."""
import copy
import importlib
import json
from types import SimpleNamespace

import pytest

from DeviceServers.control.elyse_acq.control_client import ControlClient, ControlBridge
from DeviceServers.control.elyse_acq.federated_telemetry import (
    FederatedTelemetryStore, load_federation_configuration,
)
from legacy.xp_acq_control.elyse_agent.command_protocol import OPERATIONS
from legacy.xp_acq_control.elyse_agent.federation_wire import owner_frame
from legacy.xp_acq_control.elyse_agent.standard_banks import INPUTS
from tests.unit.test_acq_federated_telemetry import KEYS, body, request, record, frame, part


def command(owner="supervision", operation="counter_timing.set"):
    return dict(command_id="f" * 32, session_id=("a" if owner == "acquisition" else "b") * 32,
                expected_revision=7, operation=operation, operator_confirmed=True,
                value=dict(counter=2, delay_us=1., width_us=2.) if operation == "counter_timing.set" else None)


@pytest.fixture
def federated_facade(monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    device = module.DS_AcqTelemetry()
    device._federated, device._closing, device._python_source = True, False, True
    device.commands_enabled = True
    store = FederatedTelemetryStore(KEYS, clock=lambda: 0.)
    records = {}
    for name, (native, kind, number, count, field, wire_kind) in INPUTS.items():
        records[name] = record(name, [False if wire_kind == "Boolean" else 20.] * count)
    store.accept(request(body(owner_frame("acquisition", "a" * 32, 1, records, "PYTHON_NATIVE"))))
    store.accept(request(body(frame("supervision", counter=part()))))
    views, calls = {}, {"acquisition": [], "supervision": []}
    for role in ("acquisition", "supervision"):
        runtime = dict(session_id=("a" if role == "acquisition" else "b") * 32, state_revision=7,
            telemetry_delivery=dict(source_mode="PYTHON_NATIVE"),
            control=dict(capabilities={name: dict(enabled=True, reason="") for name in OPERATIONS}),
            cooling_safety=dict(active=False))
        views[role] = dict(runtime=runtime, quality="FRESH" if role == "acquisition" else "READY",
                           commands_enabled=True, bridge_error="", bridge_age_seconds=.1,
                           owner_state_current=role == "supervision")
    device._store = store
    device._bridges = {role: SimpleNamespace(snapshot=lambda role=role: copy.deepcopy(views[role]))
                       for role in views}
    device._clients = {role: SimpleNamespace(submit=lambda value, role=role:
        calls[role].append(value) or dict(outcome="QUEUED")) for role in views}
    device._bridge, device._client = device._bridges["acquisition"], device._clients["acquisition"]
    yield device, store, views, calls
    store.close()


def test_supervision_intent_only_reaches_its_bound_owner(federated_facade):
    device, store, views, calls = federated_facade
    result = device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision", request=command())))
    assert json.loads(result)["outcome"] == "QUEUED"
    assert calls["supervision"] == [command()] and calls["acquisition"] == []
    assert device._control_view("supervision")["owner_state_current"] is True


def test_default_execute_command_remains_acquisition_only(federated_facade):
    device, store, views, calls = federated_facade
    value = command("acquisition", "modulator.general.start")
    device.ExecuteCommand(json.dumps(value))
    assert calls["acquisition"] == [value] and calls["supervision"] == []


def test_owner_key_and_runtime_session_cannot_be_swapped(federated_facade):
    device, store, views, calls = federated_facade
    value = command()
    value["session_id"] = "a" * 32
    with pytest.raises(RuntimeError, match="OWNER_RUNTIME_SESSION_OR_REVISION_CHANGED"):
        device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision", request=value)))
    assert not any(calls.values())


def test_supervision_cannot_claim_machine_stage_authority_even_if_bad_runtime_enables_it(federated_facade):
    device, store, views, calls = federated_facade
    with pytest.raises(RuntimeError, match="NOT_OWNED_BY_SUPERVISION"):
        device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision",
            request=command("supervision", "modulator.general.start"))))
    assert not device._control_view("supervision")["runtime"]["control"]["capabilities"]["modulator.general.stop"]["enabled"]
    assert not any(calls.values())


@pytest.mark.parametrize("mode", ["LABVIEW_BRIDGE", "TRANSITION_OR_FAULT", None])
def test_unknown_or_vi_mode_never_authorizes_remote_card_commands(federated_facade, mode):
    device, store, views, calls = federated_facade
    views["supervision"]["runtime"]["telemetry_delivery"]["source_mode"] = mode
    with pytest.raises(RuntimeError, match="OWNER_COMMANDS_DISABLED"):
        device.ExecuteOwnerCommand(json.dumps(dict(owner="supervision", request=command())))
    assert not any(calls.values())


def test_lost_supervision_source_does_not_disable_acquisition_inputs_or_explicit_stop(federated_facade):
    device, store, views, calls = federated_facade
    store.owners["supervision"]["latest"] = None
    assert device._control_view("acquisition")["telemetry_source_current"]
    assert not device._control_view("supervision")["telemetry_source_current"]
    device.ExecuteCommand(json.dumps(command("acquisition", "modulator.general.stop")))
    assert len(calls["acquisition"]) == 1 and not calls["supervision"]


def test_orchestrators_attribute_keeps_two_separate_boots(federated_facade):
    device, store, views, calls = federated_facade
    value = json.loads(device.orchestrators_json())
    assert value["federated"] and set(value["owners"]) == {"acquisition", "supervision"}
    assert value["owners"]["acquisition"]["runtime"]["session_id"] != value["owners"]["supervision"]["runtime"]["session_id"]
    assert len(json.loads(device.telemetry_json())["publications"]) == 27


def test_video_attribute_is_separate_from_runtime_and_27_bank_metadata(federated_facade):
    from tests.unit.test_acq_federated_video import video, source
    device, store, views, calls = federated_facade
    store.accept(request(body(source(sequence=2, image=video()), message=2)))
    image = json.loads(device.video_json())
    telemetry = json.loads(device.telemetry_json())
    assert image["available"] and image["frame"]["data"] == video()["data"]
    assert "frame" not in telemetry["video_metadata"] and "data" not in telemetry["video_metadata"]
    assert "video_frame" not in json.loads(device.orchestrators_json())["owners"]["supervision"]["runtime"]


def test_control_client_fixed_owner_address_and_variant():
    with pytest.raises(ValueError):
        ControlClient(b"r" * 32, host="10.20.30.2")
    with pytest.raises(ValueError):
        ControlClient(b"r" * 32, host="10.20.30.10", owner="supervision")
    client = ControlClient(b"r" * 32, host="10.20.30.2", owner="supervision")
    from tests.web.test_acq_control_api import view_fixture
    value = view_fixture()["runtime"]
    client._exchange = lambda *args: copy.deepcopy(value)
    with pytest.raises(ValueError):
        client.read()
    value["server_variant"] = "supervision_control_vnext"
    assert client.read()["server_variant"] == "supervision_control_vnext"


def test_supervision_owner_readiness_does_not_fabricate_acquisition_measurements():
    value = dict(state="RUNNING", stale=False, error="", session_id="b" * 32,
        build_id="c" * 64, state_revision=1, age_seconds=.1, control=dict(enabled=True),
        card_health=dict(all_required_ready=True),
        latest=dict(source="python_supervision_card_processes", simulated=False))
    now = [0.]
    client = SimpleNamespace(owner="supervision", enabled=True, read=lambda: copy.deepcopy(value))
    bridge = ControlBridge(client, clock=lambda: now[0])
    bridge.poll_once()
    current = bridge.snapshot()
    assert current["quality"] == "READY" and current["owner_state_current"]
    assert not current["source_current"] and current["measurements_hidden"]
    assert "banks" not in current["runtime"]["latest"]
    now[0] = 2.
    expired = bridge.snapshot()
    assert not expired["owner_state_current"] and expired["runtime"]["latest"] is None


def test_actual_supervision_snapshot_is_ready_with_top_level_health_and_no_acquisition_banks():
    from tests.unit.test_two_orchestrator_end_to_end import supervision_runtime_with_ram_owners
    runtime = supervision_runtime_with_ram_owners()
    actual = runtime.snapshot()
    assert actual["card_health"]["all_required_ready"] is True
    assert "card_health" not in actual["latest"]
    assert actual["latest"]["banks"] == {}
    client = ControlClient(b"r" * 32, b"w" * 32, enabled=True,
                           host="10.20.30.2", owner="supervision")
    client._exchange = lambda *args: runtime.snapshot()
    bridge = ControlBridge(client, clock=lambda: 0.)
    bridge.poll_once()
    current = bridge.snapshot()
    assert current["quality"] == "READY" and current["owner_state_current"]
    assert current["runtime"]["control"]["capabilities"]["counter_timing.set"]["enabled"]
    assert not current["source_current"] and current["measurements_hidden"]
    assert runtime._thread is None


@pytest.mark.parametrize("phase", ["pending", "executing"])
def test_actual_supervision_pending_or_executing_timing_never_enables_another_timing(phase):
    from tests.unit.test_two_orchestrator_end_to_end import supervision_runtime_with_ram_owners
    runtime = supervision_runtime_with_ram_owners()
    if phase == "pending":
        runtime._pending = ("timing", dict(counter=2, delay_us=1., width_us=2.))
    else:
        runtime.dispatch_remote("counter_timing.set", dict(counter=2, delay_us=1., width_us=2.))
    client = SimpleNamespace(owner="supervision", enabled=True, read=runtime.snapshot)
    bridge = ControlBridge(client, clock=lambda: 0.)
    bridge.poll_once()
    current = bridge.snapshot()
    assert not current["runtime"]["control"]["capabilities"]["counter_timing.set"]["enabled"]
    assert runtime.counter_memory_part() is None
    if phase == "executing":
        assert not current["owner_state_current"] and current["runtime"]["latest"] is None
    assert runtime._thread is None


def test_local_configuration_requires_four_independent_active_keys(tmp_path):
    owner_config = {}
    for index, role in enumerate(("acquisition", "supervision")):
        read, command_path = tmp_path / (role + ".read"), tmp_path / (role + ".write")
        read.write_bytes(("r" + str(index)).encode() * 32)
        command_path.write_bytes(("w" + str(index)).encode() * 32)
        owner_config[role] = dict(host="10.20.30.10" if role == "acquisition" else "10.20.30.2",
            port=8772, read_key_file=read.name, command_key_file=command_path.name, commands_enabled=True)
    path = tmp_path / "federation.json"
    path.write_text(json.dumps(dict(schema_version=1, owners=owner_config)))
    value = load_federation_configuration(path, commands_enabled=True)
    assert all(item["enabled"] for item in value.values())
    assert value["supervision"]["host"] == "10.20.30.2"
    (tmp_path / owner_config["supervision"]["read_key_file"]).write_bytes(value["acquisition"]["read_key"])
    with pytest.raises(ValueError, match="must differ"):
        load_federation_configuration(path, commands_enabled=True)
