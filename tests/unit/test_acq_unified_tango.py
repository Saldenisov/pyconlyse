"""Exercise the real facade methods against fake read stores and clients."""
import copy
import importlib
import json
from types import SimpleNamespace

import pytest


def intent(operation="modulator.general.start"):
    return json.dumps(dict(command_id="b" * 32, session_id="a" * 32, expected_revision=7,
                           operation=operation, operator_confirmed=True, value=None))


@pytest.fixture
def facade(monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, "run", lambda *args, **kwargs: None, raising=False)
    module = importlib.import_module("DeviceServers.control.elyse_acq.DS_AcqTelemetry")
    device = module.DS_AcqTelemetry()
    device._python_source = True
    device._closing = False
    device.commands_enabled = True
    calls = []
    view = dict(source="xp_python_acquisition_control", commands_enabled=True, quality="FRESH",
                bridge_age_seconds=.1, bridge_error="", runtime=dict(session_id="a" * 32,
                cooling_safety=dict(schema_version=1, active=False)))
    from legacy.xp_acq_control.elyse_agent.native_telemetry import INPUTS
    snapshot = dict(source="python_daqmx_acquisition", publications={
        name:dict(session_id="a" * 32, producer_kind="python_acquisition", stale=False,
                  error=dict(status=False, code=0, source="")) for name in INPUTS})
    device._bridge = SimpleNamespace(snapshot=lambda: copy.deepcopy(view))
    device._store = SimpleNamespace(snapshot=lambda: copy.deepcopy(snapshot))
    device._client = SimpleNamespace(submit=lambda request: calls.append(request) or dict(outcome="QUEUED"))
    return device, view, snapshot, calls


def test_same_device_routes_only_confirmed_current_python_source(facade):
    device, view, snapshot, calls = facade
    assert device._control_view()["commands_enabled"] is True
    assert json.loads(device.telemetry_json())["cooling_safety"]["schema_version"] == 1
    # This request reaches a fake client only, never an HTTP/device boundary.
    assert json.loads(device.ExecuteCommand(intent()))["outcome"] == "QUEUED"
    assert len(calls) == 1


@pytest.mark.parametrize("defect", ["labview", "disabled", "closing", "missing", "stale", "old_boot", "read_error", "metadata_missing"])
def test_no_command_without_matching_current_pushed_telemetry(facade, defect):
    device, view, snapshot, calls = facade
    if defect == "labview": device._python_source = False
    if defect == "disabled": device.commands_enabled = False
    if defect == "closing": device._closing = True
    if defect == "missing": snapshot["publications"] = {}
    if defect == "metadata_missing": view["runtime"] = None
    for packet in snapshot["publications"].values():
        if defect == "stale": packet["stale"] = True
        if defect == "old_boot": packet["session_id"] = "b" * 32
        if defect == "read_error": packet["error"]["status"] = True
    with pytest.raises(RuntimeError, match="TANGO_COMMANDS_DISABLED"):
        device.ExecuteCommand(intent())
    assert calls == []


def test_stale_metadata_does_not_claim_current_owner_cooling_policy(facade):
    device, view, snapshot, calls = facade
    view["bridge_age_seconds"] = 3
    assert json.loads(device.telemetry_json())["cooling_safety"] is None


def test_stale_push_does_not_hide_explicit_stop_when_current_owner_is_authenticated(facade):
    device, view, snapshot, calls = facade
    snapshot["publications"] = {}
    assert not device._control_view()["telemetry_source_current"]
    assert json.loads(device.ExecuteCommand(intent("modulator.general.stop")))["outcome"] == "QUEUED"
    assert len(calls) == 1
    view["bridge_age_seconds"] = 3
    with pytest.raises(RuntimeError, match="TANGO_COMMANDS_DISABLED"):
        device.ExecuteCommand(intent("modulator.general.stop"))


@pytest.mark.parametrize('mode', ['LABVIEW_BRIDGE', 'TRANSITION_OR_FAULT'])
def test_unified_bridge_and_transition_have_no_equipment_command_authority(facade, mode):
    device, view, snapshot, calls = facade
    view['runtime']['telemetry_delivery'] = dict(source_mode=mode)
    assert device._control_view()['commands_enabled'] is False
    with pytest.raises(RuntimeError, match='TANGO_COMMANDS_DISABLED'):
        device.ExecuteCommand(intent('modulator.general.stop'))
    assert not calls


def test_status_only_snapshot_reaches_receiver_tango_and_web_without_start_permit(facade, monkeypatch):
    """Actual receiver expansion + facade + browser projection, no live Tango."""
    from pathlib import Path
    from uuid import uuid4
    from DeviceServers.control.elyse_acq.telemetry_sink import TelemetrySinkStore
    from legacy.xp_acq_control.elyse_agent.telemetry_relay import sign
    from tests.unit.test_acq_command_telemetry_pipeline import Runtime, image, KEY
    from legacy.xp_acq_control.elyse_agent.dual_mode_telemetry import DualModeTelemetryPublisher
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'web/backend'))
    web = importlib.import_module('acq_telemetry_api')
    device, view, unused, calls = facade
    store = TelemetrySinkStore(KEY, permitted_producer_kind='unified_acquisition')
    runtime = Runtime(image())
    publisher = DualModeTelemetryPublisher(runtime, ('127.0.0.1', 1), KEY)
    device._store = store
    view['runtime']['telemetry_delivery'] = dict(source_mode='PYTHON_NATIVE')
    try:
        runtime.value['software_state']['local_banks']['DPS'][2] = True
        for completed in (False, True):
            if completed:
                runtime.update_status(eps=((8, True),), dps=((2, False),))
            assert publisher.publish_once()
            body = publisher.outbox.peek()
            request = dict(body=body, nonce=uuid4().hex)
            request['signature'] = sign(KEY, 'ACQ-TELEMETRY-REQUEST-1', request)
            store.accept(request)
            publisher.outbox.acknowledge(body['relay_id'], body['message_id'])
            browser = web.present_snapshot(device.telemetry_json(), 'ON')
            banks = browser['snapshot']['publications']
            assert len(banks) == 27
            assert banks['DPS']['data'][2] is not completed
            assert banks['EPS']['data'][8] is completed
            assert banks['C2NI6071E']['data'] is None
            assert browser['quality'] == 'INCOMPLETE'
            assert browser['execution_allowed'] is False
            assert not device._control_view()['telemetry_source_current']
            with pytest.raises(RuntimeError, match='TANGO_COMMANDS_DISABLED'):
                device.ExecuteCommand(intent())
        assert calls == []
    finally:
        publisher.close()
        store.close()
