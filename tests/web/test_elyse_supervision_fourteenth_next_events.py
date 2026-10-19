"""G75 source-specific stateless web replays; no configured provider access."""
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
from fourteenth_next_event_fixtures import (
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
    app.config.update(TESTING=True, JWT_SECRET_KEY='G75-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_23143 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_23770 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_23143, saved_sup_event_23770
    assert acq.replay_event is saved_acq_event_23143.replay_event
    assert acq.replay_saved_acq_event_23143 is saved_acq_event_23143.replay_saved_acq_event_23143
    assert sup.project_event_23770 is saved_sup_event_23770.project_event_23770
    assert sup.replay_saved_sup_event_23770 is saved_sup_event_23770.replay_saved_sup_event_23770


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_23143', acq_payload), ('saved_acq_event_23143', false_acq_payload),
    ('saved_acq_event_23143', inflight_acq_payload), ('saved_sup_event_23770', sup_payload),
    ('saved_sup_event_23770', minimal_sup_payload), ('saved_sup_event_23770', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_23143 import replay_saved_acq_event_23143
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_23770 import replay_saved_sup_event_23770
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_23143 if operation == 'saved_acq_event_23143' else replay_saved_sup_event_23770
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_eight_source_stages_and_independent_publication_read(client):
    p = acq_payload(); response = post(client, 'saved_acq_event_23143', p)
    assert response.status_code == 200
    result = response.get_json()['result']; writes = {row['node_uid']: row['value'] for row in result['writes']}
    expected = {}
    for uid, read, fields in (('24413', '24474', {5: True}), ('26145', '27893', {5: False}),
            ('28881', '28916', {2: True}), ('28962', '28978', {2: False}),
            ('29062', '29087', {23: False, 20: True, 18: False}), ('29094', '29175', {6: False})):
        carrier = list(p['snapshots'][read])
        for index, value in fields.items(): carrier[index] = value
        expected[uid] = carrier
    expected['24495'] = True
    assert writes == expected
    assert result['completed_stages'] == ['24338', '25366', '28640', '28837', '28946', '28995', '29025', '29203']
    calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
    assert calls['29442']['29569'] == p['snapshots']['29424'] != writes['29094']
    assert calls['29616']['29732'] == p['leaf_returns']['29442']['29560']
    for uid, ports in (('24789', {'24815': 150}), ('28736', {'28820': 500}),
            ('28924', {'28929': 150}), ('29013', {'29018': 250}), ('29398', {'29415': 100})):
        assert calls[uid] == ports
    assert result['scheduler_qualified'] is False
    assert result['native_callee_equivalence'] is False


@pytest.mark.parametrize('uid', ['25991', '28952', '29031', '29052', '40005'])
@pytest.mark.parametrize('value', [True, 0, None, 'False', 0.0])
def test_acq_exact_false_carriers_refuse_hypothesis_expansion(client, uid, value):
    p = acq_payload(); p['literal_inputs'][uid] = value
    assert post(client, 'saved_acq_event_23143', p).status_code == 400
    p = acq_payload(); del p['literal_inputs'][uid]
    assert post(client, 'saved_acq_event_23143', p).status_code == 400


def test_acq_false_inflight_and_extra_keys_are_source_specific(client):
    response = post(client, 'saved_acq_event_23143', false_acq_payload())
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '24286' and result['writes'] == result['leaf_calls'] == []
    p = inflight_acq_payload(); response = post(client, 'saved_acq_event_23143', p)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['pending_leaf_uids'] == ['24789'] and result['active_stage'] == '24338'
    assert result['selected_body_completed'] is False
    p['schedule'].append(dict(kind='stage_complete', uid='24338'))
    assert post(client, 'saved_acq_event_23143', p).status_code == 400
    p = acq_payload(); p['field_index_bindings'] = {}
    assert post(client, 'saved_acq_event_23143', p).status_code == 400
    p = acq_payload(); p['reference_bindings']['29221']['saved_uri'] += '/other'
    assert post(client, 'saved_acq_event_23143', p).status_code == 400
    p = acq_payload(); p['unwired_inputs']['29723'] = 65536
    assert post(client, 'saved_acq_event_23143', p).status_code == 400


@pytest.mark.parametrize('first', [False, True])
@pytest.mark.parametrize('second', [False, True])
@pytest.mark.parametrize('reset', [False, True])
def test_sup_two_independent_c5_carriers_three_phases_field24_and_reset_fanout(client, first, second, reset):
    p = sup_payload(); p['literal_inputs'] = {'78270': first, '78499': second, '82173': reset}
    response = post(client, 'saved_sup_event_23770', p); assert response.status_code == 200
    result = response.get_json()['result']; assert result['selected_case_frame'] == '78236'
    assert result['source_sequence_actual_diagram_uids'] == ['78246', '78446', '78475']
    calls = {row['node_uid']: row for row in result['leaf_observations']}
    assert [row['sequence_phase'] for row in result['leaf_observations']] == [0, 0, 1, 2, 2]
    for index, read, writer, port, value in ((0, '78286', '78302', '78395', first), (1, '78515', '78531', '78545', second)):
        expected = list(p['local_reads'][read]); expected[24] = value
        assert result['local_assignments'][index]['value'] == calls[writer]['inputs'][port] == expected
        assert result['field_updates'][index]['raw_flattened_field_index'] == 24
        assert result['field_updates'][index]['typed_position_path'] == [24]
        assert result['field_updates'][index]['field_label'] == '24 DPB0 b82 Cmd Faraday 2 EN'
    assert result['local_assignments'][0]['value'] != result['local_assignments'][1]['value']
    assert calls['78302']['inputs']['78304'] == p['reference_bindings']['78252']['native_reference']
    assert calls['78531']['inputs']['78533'] == p['reference_bindings']['78481']['native_reference']
    assert calls['78398']['inputs']['78428'] == p['native_boundaries']['78302']['outputs']['78392']
    assert calls['78548']['inputs']['78600'] == p['native_boundaries']['78531']['outputs']['78542']
    assert calls['78464']['inputs'] == {'78469': 500}
    assert [(row['node_uid'], row['explicit_paramIdx'], row['value']) for row in result['local_assignments'][2:]] == [
        ('82122', 156, reset), ('15517', 10, reset), ('82078', 7, reset)]
    assert result['native_field_index_selection_qualified'] is False
    assert result['native_wait_units_or_timing_qualified'] is False


def test_sup_empty_false_arm_and_caller_completion_observations(client):
    response = post(client, 'saved_sup_event_23770', minimal_sup_payload()); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '77941' and result['leaf_observations'] == result['local_assignments'] == []
    p = sup_payload(); p['completed_sinks'] = ['78548', '78280']
    response = post(client, 'saved_sup_event_23770', p); assert response.status_code == 200
    result = response.get_json()['result']; assert result['completed_sinks'] == p['completed_sinks']
    assert result['completion_observations_are_feasible_trace'] is False


def test_sup_carrier_literal_reference_error_and_native_boundary_refusals(client):
    mutants = []
    for uid in ('78286', '78515'):
        for value in ([False] * 39, [False] * 41, [0] * 40):
            p = sup_payload(); p['local_reads'][uid] = value; mutants.append(p)
    for uid in ('78270', '78499', '82173'):
        p = sup_payload(); p['literal_inputs'][uid] = 0; mutants.append(p)
        p = sup_payload(); del p['literal_inputs'][uid]; mutants.append(p)
    p = sup_payload(); p['reference_bindings']['78252']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['78302']['outputs']['78392']['status'] = 0; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['78531']['outputs']['78542']['code'] = 2**31; mutants.append(p)
    p = sup_payload(); del p['unwired_inputs']['78539']; mutants.append(p)
    p = sup_payload(); p['unwired_inputs']['78425'] = 65536; mutants.append(p)
    for report in (['78548', '78548'], ['78646']):
        p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
    for p in mutants: assert post(client, 'saved_sup_event_23770', p).status_code == 400
    p = sup_payload(); p['unwired_inputs']['78413'] = {'bytes_hex': '00FF'}
    response = post(client, 'saved_sup_event_23770', p); assert response.status_code == 200
    assert response.get_json()['result']['leaf_observations'][1]['inputs']['78413'] == {'bytes_hex': '00FF'}
    p['unwired_inputs']['78413'] = {'bytes_hex': 'ff'}
    assert post(client, 'saved_sup_event_23770', p).status_code == 400


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_23143', acq_payload), ('saved_sup_event_23770', sup_payload)])
def test_exact_identity_and_no_execution_extension(client, operation, factory):
    for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
        p = factory(); p[key] = 'wrong'; assert post(client, operation, p).status_code == 400
    p = factory(); p['execute_native'] = True; assert post(client, operation, p).status_code == 400


def test_actual_request_cap_and_distinct_web_response_policy(client):
    p = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_23770', inputs=p), ensure_ascii=False, separators=(',', ':')).encode('utf8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200 and len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X' * 65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_23770","operation":"saved_sup_event_23770","inputs":{}}',
                b'{"operation":"saved_sup_event_23770","inputs":{"event_outputs":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False
