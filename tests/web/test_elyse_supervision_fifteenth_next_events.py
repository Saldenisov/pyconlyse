"""G76 source-specific stateless web replays; no configured provider access."""
import copy
import importlib
import json
from pathlib import Path
import sys
import pytest
from flask import Flask
from flask_jwt_extended import JWTManager

REPO = next(p for p in Path(__file__).resolve().parents
            if (p / 'legacy/xp_acq_agent').is_dir() and (p / 'web/backend').is_dir())
sys.path.insert(0, str(REPO / 'web/backend'))
sys.path.insert(0, str(REPO / 'legacy/xp_acq_agent/tests'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fifteenth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload)
api = importlib.import_module('elyse_supervision_api')


def unusable_provider(*args, **kwargs):
    raise AssertionError('Stateless replay accessed provider/business/native runtime')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    monkeypatch.setattr(api, 'configured_acq', unusable_provider)
    monkeypatch.setattr(api, 'business', unusable_provider)
    app = Flask(__name__)
    app.config.update(TESTING=True, JWT_SECRET_KEY='G76-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_35942 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_56943 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_35942, saved_sup_event_56943
    assert acq.replay_event is saved_acq_event_35942.replay_event
    assert acq.replay_saved_acq_event_35942 is saved_acq_event_35942.replay_saved_acq_event_35942
    assert sup.project_event_56943 is saved_sup_event_56943.project_event_56943
    assert sup.replay_saved_sup_event_56943 is saved_sup_event_56943.replay_saved_sup_event_56943


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_35942', acq_payload), ('saved_acq_event_35942', false_acq_payload),
    ('saved_acq_event_35942', inflight_acq_payload), ('saved_sup_event_56943', sup_payload),
    ('saved_sup_event_56943', minimal_sup_payload), ('saved_sup_event_56943', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_35942 import replay_saved_acq_event_35942
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_56943 import replay_saved_sup_event_56943
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_35942 if operation == 'saved_acq_event_35942' else replay_saved_sup_event_56943
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_eight_source_stages_and_independent_publication_read(client):
    p = acq_payload(); response = post(client, 'saved_acq_event_35942', p)
    assert response.status_code == 200
    result = response.get_json()['result']; writes = {row['node_uid']: row['value'] for row in result['writes']}
    expected = {}
    for uid, read, fields in (('36049', '36067', {16: True}), ('36131', '36147', {16: False}),
            ('36209', '36226', {2: True}), ('36271', '36287', {2: False}),
            ('36370', '36391', {29: False, 26: True, 24: False}), ('36397', '36415', {8: False})):
        carrier = list(p['snapshots'][read])
        for index, value in fields.items(): carrier[index] = value
        expected[uid] = carrier
    expected['36073'] = True
    assert writes == expected
    assert result['completed_stages'] == ['36023', '36115', '36163', '36193', '36255', '36304', '36334', '36443']
    calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
    assert calls['36493']['36507'] == p['snapshots']['36487'] != writes['36397']
    assert calls['36510']['36541'] == p['leaf_returns']['36493']['36504']
    for uid, ports in (('36081', {'36086': 150}), ('36181', {'36186': 500}),
            ('36232', {'36238': 150}), ('36322', {'36327': 250}), ('36479', {'36484': 100})):
        assert calls[uid] == ports
    assert result['scheduler_qualified'] is False
    assert result['native_callee_equivalence'] is False


@pytest.mark.parametrize('uid', ['36121', '36261', '36340', '36360', '42575'])
@pytest.mark.parametrize('value', [True, 0, None, 'False', 0.0])
def test_acq_exact_false_carriers_refuse_hypothesis_expansion(client, uid, value):
    p = acq_payload(); p['literal_inputs'][uid] = value
    assert post(client, 'saved_acq_event_35942', p).status_code == 400
    p = acq_payload(); del p['literal_inputs'][uid]
    assert post(client, 'saved_acq_event_35942', p).status_code == 400


def test_acq_false_inflight_and_extra_keys_are_source_specific(client):
    response = post(client, 'saved_acq_event_35942', false_acq_payload())
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '35996' and result['writes'] == result['leaf_calls'] == []
    p = inflight_acq_payload(); response = post(client, 'saved_acq_event_35942', p)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['pending_leaf_uids'] == ['36081'] and result['active_stage'] == '36023'
    assert result['selected_body_completed'] is False
    p['schedule'].append(dict(kind='stage_complete', uid='36023'))
    assert post(client, 'saved_acq_event_35942', p).status_code == 400
    p = acq_payload(); p['field_index_bindings'] = {}
    assert post(client, 'saved_acq_event_35942', p).status_code == 400
    p = acq_payload(); p['reference_bindings']['36461']['saved_uri'] += '/other'
    assert post(client, 'saved_acq_event_35942', p).status_code == 400
    p = acq_payload(); p['unwired_inputs']['36538'] = 65536
    assert post(client, 'saved_acq_event_35942', p).status_code == 400


@pytest.mark.parametrize('first', [False, True])
@pytest.mark.parametrize('second', [False, True])
@pytest.mark.parametrize('reset', [False, True])
def test_sup_two_independent_c5_carriers_three_phases_field25_and_reset_fanout(client, first, second, reset):
    p = sup_payload(); p['literal_inputs'] = {'62607': first, '62918': second, '72708': reset}
    response = post(client, 'saved_sup_event_56943', p); assert response.status_code == 200
    result = response.get_json()['result']; assert result['source_case_uid'] == '57006'
    assert result['source_NewVal_terminal_uid'] == '56998' and result['selected_case_frame'] == '62568'
    assert result['source_sequence_actual_diagram_uids'] == ['62578', '62813', '62872']
    calls = {row['node_uid']: row for row in result['leaf_observations']}
    assert [row['sequence_phase'] for row in result['leaf_observations']] == [0, 0, 1, 2, 2]
    for index, read, writer, port, value in ((0, '62631', '62647', '62667', first), (1, '62938', '62956', '62972', second)):
        expected = list(p['local_reads'][read]); expected[25] = value
        assert result['local_assignments'][index]['value'] == calls[writer]['inputs'][port] == expected
        assert result['field_updates'][index]['raw_flattened_field_index'] == 25
        assert result['field_updates'][index]['typed_position_path'] == [25]
        assert result['field_updates'][index]['field_label'] == '25 DPB1 b80 Cmd Faraday 3 EN'
    assert result['local_assignments'][0]['value'] != result['local_assignments'][1]['value']
    assert calls['62647']['inputs']['62649'] == p['reference_bindings']['62584']['native_reference']
    assert calls['62956']['inputs']['62958'] == p['reference_bindings']['62881']['native_reference']
    assert calls['62674']['inputs']['62763'] == p['native_boundaries']['62647']['outputs']['62663']
    assert calls['62975']['inputs']['63023'] == p['native_boundaries']['62956']['outputs']['62969']
    assert calls['62840']['inputs'] == {'62865': 500}
    assert [(row['node_uid'], row['explicit_paramIdx'], row['value']) for row in result['local_assignments'][2:]] == [
        ('72697', 156, reset), ('72654', 10, reset), ('72689', 7, reset)]
    assert result['native_field_index_selection_qualified'] is False
    assert result['native_wait_units_or_timing_qualified'] is False


def test_sup_empty_false_arm_and_caller_completion_observations(client):
    response = post(client, 'saved_sup_event_56943', minimal_sup_payload()); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '57045' and result['leaf_observations'] == result['local_assignments'] == []
    p = sup_payload(); p['completed_sinks'] = ['62975', '62619']
    response = post(client, 'saved_sup_event_56943', p); assert response.status_code == 200
    result = response.get_json()['result']; assert result['completed_sinks'] == p['completed_sinks']
    assert result['completion_observations_are_feasible_trace'] is False


def test_sup_carrier_literal_reference_error_and_native_boundary_refusals(client):
    mutants = []
    for uid in ('62631', '62938'):
        for value in ([False] * 39, [False] * 41, [0] * 40):
            p = sup_payload(); p['local_reads'][uid] = value; mutants.append(p)
    for uid in ('62607', '62918', '72708'):
        p = sup_payload(); p['literal_inputs'][uid] = 0; mutants.append(p)
        p = sup_payload(); del p['literal_inputs'][uid]; mutants.append(p)
    p = sup_payload(); p['reference_bindings']['62584']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['62647']['outputs']['62663']['status'] = 0; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['62956']['outputs']['62969']['code'] = 2**31; mutants.append(p)
    p = sup_payload(); del p['unwired_inputs']['62965']; mutants.append(p)
    p = sup_payload(); p['unwired_inputs']['62754'] = 65536; mutants.append(p)
    for report in (['62975', '62975'], ['63056']):
        p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
    for p in mutants: assert post(client, 'saved_sup_event_56943', p).status_code == 400
    p = sup_payload(); p['unwired_inputs']['62699'] = {'bytes_hex': '00FF'}
    response = post(client, 'saved_sup_event_56943', p); assert response.status_code == 200
    assert response.get_json()['result']['leaf_observations'][1]['inputs']['62699'] == {'bytes_hex': '00FF'}
    p['unwired_inputs']['62699'] = {'bytes_hex': 'ff'}
    assert post(client, 'saved_sup_event_56943', p).status_code == 400


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_35942', acq_payload), ('saved_sup_event_56943', sup_payload)])
def test_exact_identity_and_no_execution_extension(client, operation, factory):
    for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
        p = factory(); p[key] = 'wrong'; assert post(client, operation, p).status_code == 400
    p = factory(); p['execute_native'] = True; assert post(client, operation, p).status_code == 400


def test_actual_request_cap_and_distinct_web_response_policy(client):
    p = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_56943', inputs=p), ensure_ascii=False, separators=(',', ':')).encode('utf8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200 and len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X' * 65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_56943","operation":"saved_sup_event_56943","inputs":{}}',
                b'{"operation":"saved_sup_event_56943","inputs":{"event_outputs":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False
