"""One fake Everest device for reads and named writes; no XP/NI interaction."""
import json
from types import SimpleNamespace

import pytest

from tests.web.test_acq_control_api import setup_api, api, ROOT, request_command
from tests.web.test_acq_telemetry_api import snapshot
from web.backend import acq_contract
import acq_telemetry_api as telemetry_api
from legacy.xp_acq_agent.elyse_agent.cooling_safety import CoolingSafety


@pytest.fixture
def unified(setup_api, monkeypatch):
    app, client, headers, view, original_calls, unused = setup_api
    app.register_blueprint(telemetry_api.acq_telemetry_api)
    packet = snapshot()
    packet['source'] = 'python_daqmx_acquisition'
    packet['cooling_safety'] = CoolingSafety().snapshot()
    calls = []

    class Device:
        def set_timeout_millis(self, timeout):
            pass

        def read_attribute(self, name):
            calls.append(('attribute', name))
            assert name == 'runtime_json'
            return SimpleNamespace(has_failed=False, value=json.dumps(view))

        def read_attributes(self, names):
            calls.append(('attributes', names))
            assert names == ['State', 'telemetry_json']
            return [SimpleNamespace(has_failed=False, value='ON'),
                    SimpleNamespace(has_failed=False, value=json.dumps(packet))]

        def command_inout(self, name, raw):
            intent = json.loads(raw)
            calls.append(('command', name, intent))
            assert name == 'ExecuteCommand'
            return json.dumps(dict(command_id=intent['command_id'], session_id=intent['session_id'],
                operation=intent['operation'], outcome='QUEUED', hardware_acknowledged=False))

    def device(name):
        calls.append(('device', name))
        assert name == acq_contract.DEVICE  # Any second DS fails the fixture.
        return Device()
    monkeypatch.setattr(api.tango_gateway, 'create_device_proxy', device)
    return app, client, headers, view, packet, calls


def test_all_live_reads_and_named_writes_share_the_one_telemetry_device(unified):
    app, client, headers, view, packet, calls = unified
    raw = client.get('/api/elyse/acquisition/telemetry')
    control = client.get(ROOT)
    cooling = client.get('/api/elyse/acquisition/telemetry/cooling')
    assert raw.status_code == control.status_code == cooling.status_code == 200
    assert len(raw.json['snapshot']['publications']) == 27
    assert control.json['source_mode'] == 'PYTHON_NATIVE'
    assert cooling.json['source'] == 'xp_control'
    assert raw.json['topology'] == control.json['topology'] == cooling.json['topology'] == acq_contract.topology()
    intent = request_command(operation='ht_voltage.set', value=6.7)
    reply = client.post(ROOT + '/commands', json=intent, headers=headers)
    assert reply.status_code == 200
    assert [row for row in calls if row[0] == 'command'] == [('command', 'ExecuteCommand', intent)]
    assert {row[1] for row in calls if row[0] == 'device'} == {acq_contract.DEVICE}
    assert api.DEVICE == telemetry_api.DEVICE == acq_contract.DEVICE


@pytest.mark.parametrize('mode', ['LABVIEW_BRIDGE', 'TRANSITION_OR_FAULT', None, 'other'])
def test_non_native_source_cannot_grant_commands_even_if_cached_capabilities_say_yes(unified, mode):
    app, client, headers, view, packet, calls = unified
    view['runtime']['telemetry_delivery'] = {} if mode is None else dict(source_mode=mode)
    read = client.get(ROOT)
    assert read.status_code == 200
    assert read.json['execution_allowed'] is False
    assert read.json['source_selected'] is False
    assert not any(item['enabled'] for item in read.json['capabilities'].values())
    refused = client.post(ROOT + '/commands', json=request_command(), headers=headers)
    assert refused.status_code == 409
    assert refused.json['code'] == 'acquisition_pre_dispatch_rejected'
    assert refused.json['receipt']['dispatch_attempted'] is False
    assert not any(row[0] == 'command' for row in calls)


def test_mode_changed_after_browser_confirmation_is_rechecked_without_fallback(unified):
    app, client, headers, view, packet, calls = unified
    assert client.get(ROOT).json['execution_allowed'] is True
    # The same XP process switches source; no replacement DS or browser source selector.
    view['runtime']['telemetry_delivery']['source_mode'] = 'LABVIEW_BRIDGE'
    packet['source'] = 'copied_labview_telemetry'
    view['runtime']['state'] = 'IDLE'
    refused = client.post(ROOT + '/commands', json=request_command(), headers=headers)
    assert refused.status_code == 409
    assert refused.json['receipt']['outcome'] == 'REJECTED'
    assert refused.json['receipt']['dispatch_attempted'] is False
    assert client.get(ROOT).json['commands'] == []
    assert client.get('/api/elyse/acquisition/telemetry').json['source'] == 'copied_labview_telemetry'
    assert not any(row[0] == 'command' for row in calls)


@pytest.mark.parametrize('alias', ['unified', 'labview', 'xp_control'])
def test_old_cooling_labels_do_not_select_a_different_server(unified, alias):
    app, client, headers, view, packet, calls = unified
    app.config['ELYSE_COOLING_SOURCE'] = alias
    assert client.get('/api/elyse/acquisition/telemetry/cooling').json['source'] == 'xp_control'
    packet['source'] = 'copied_labview_telemetry'
    assert client.get('/api/elyse/acquisition/telemetry/cooling').json['source'] == 'labview'
    assert {row[1] for row in calls if row[0] == 'device'} == {acq_contract.DEVICE}
