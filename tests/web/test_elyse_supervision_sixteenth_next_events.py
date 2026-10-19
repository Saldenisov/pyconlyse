"""G77 source-specific stateless web replays; no configured provider access."""
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
from sixteenth_next_event_fixtures import (
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
    app.config.update(TESTING=True, JWT_SECRET_KEY='G77-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_40079 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_53656 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_40079, saved_sup_event_53656
    assert acq.replay_event is saved_acq_event_40079.replay_event
    assert acq.replay_saved_acq_event_40079 is saved_acq_event_40079.replay_saved_acq_event_40079
    assert sup.project_event_53656 is saved_sup_event_53656.project_event_53656
    assert sup.replay_saved_sup_event_53656 is saved_sup_event_53656.replay_saved_sup_event_53656


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_40079', acq_payload), ('saved_acq_event_40079', false_acq_payload),
    ('saved_acq_event_40079', inflight_acq_payload), ('saved_sup_event_53656', sup_payload),
    ('saved_sup_event_53656', minimal_sup_payload), ('saved_sup_event_53656', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_40079 import replay_saved_acq_event_40079
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_53656 import replay_saved_sup_event_53656
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_40079 if operation == 'saved_acq_event_40079' else replay_saved_sup_event_53656
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_hierarchical_phases_wire_errors_and_independent_publication(client):
    p = acq_payload(); response = post(client, 'saved_acq_event_40079', p)
    assert response.status_code == 200
    result = response.get_json()['result']; writes = {row['node_uid']: row['value'] for row in result['writes']}
    expected = {}
    for uid, read, fields in (('40188', '40206', {7: True}), ('40261', '40277', {7: False}),
            ('40339', '40355', {2: True}), ('40399', '40415', {2: False}),
            ('40499', '40520', {35: False, 32: True, 30: False}), ('40526', '40544', {10: False})):
        carrier = list(p['snapshots'][read])
        for index, value in fields.items(): carrier[index] = value
        expected[uid] = carrier
    expected['40212'] = True
    assert writes == expected
    assert result['completed_main_stages'] == ['40162', '40245', '40293', '40323', '40383', '40432', '40463', '40573']
    assert result['completed_nested_stages'] == ['46840', '48404', '49054']
    assert result['completed_stages'] == ['40162', '40245', '46840', '48404', '49054', '40293', '40323', '40383', '40432', '40463', '40573']
    calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
    assert calls['40623']['40637'] == p['snapshots']['40617'] != writes['40526']
    assert calls['40640']['40670'] == p['leaf_returns']['40623']['40634']
    assert calls['50796']['50912'] == p['leaf_returns']['38600']['45219']
    assert calls['38600'] == {uid: p['unwired_inputs'][uid] for uid in ('45228', '45233', '45236', '45240', '45243', '45247')}
    for uid, ports in (('40220', {'40225': 150}), ('40311', {'40316': 29000}),
            ('50176', {'50185': 1500}), ('40361', {'40366': 150}), ('40451', {'40456': 250}), ('40609', {'40614': 100})):
        assert calls[uid] == ports
    assert result['scheduler_qualified'] is False and result['native_callee_equivalence'] is False


@pytest.mark.parametrize('uid', ['40251', '40389', '40469', '40489'])
@pytest.mark.parametrize('value', [True, 0, None, 'False', 0.0])
def test_acq_exact_false_literal_carriers_refuse_expansion(client, uid, value):
    p = acq_payload(); p['literal_inputs'][uid] = value
    assert post(client, 'saved_acq_event_40079', p).status_code == 400
    p = acq_payload(); del p['literal_inputs'][uid]
    assert post(client, 'saved_acq_event_40079', p).status_code == 400


def test_acq_false_and_nested_inflight_source_dependencies(client):
    response = post(client, 'saved_acq_event_40079', false_acq_payload()); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '40135' and result['writes'] == result['leaf_calls'] == []
    p = inflight_acq_payload(); response = post(client, 'saved_acq_event_40079', p); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['pending_leaf_uids'] == ['38600'] and result['active_stage'] == '48404'
    assert result['completed_main_stages'] == ['40162', '40245'] and result['completed_nested_stages'] == ['46840']
    assert result['selected_body_completed'] is False
    p['schedule'].append(dict(kind='stage_complete', uid='48404'))
    assert post(client, 'saved_acq_event_40079', p).status_code == 400
    p = acq_payload(); p['field_index_bindings'] = {}; assert post(client, 'saved_acq_event_40079', p).status_code == 400
    p = acq_payload(); p['reference_bindings']['40591']['saved_uri'] += '/other'; assert post(client, 'saved_acq_event_40079', p).status_code == 400
    p = acq_payload(); p['unwired_inputs']['50904'] = 65536; assert post(client, 'saved_acq_event_40079', p).status_code == 400


@pytest.mark.parametrize('selector,frame,diagrams,field,pairs,wait,waitport', [
    (0, '76439', ['77981', '81258', '85997'], 22,
     [('53890', '53881', '53908', '53934', '79753', '54139', '53910', '54213', '70702', '53930'),
      ('86012', '86004', '86028', '86042', '86078', '86088', '86030', '86045', '86075', '86039')], '81888', '81908'),
    (1, '56504', ['56523', '56742', '56785'], 26,
     [('56568', '56560', '56584', '56647', '56550', '56529', '56586', '56650', '56706', '56644'),
      ('56833', '56827', '56849', '56867', '56817', '56792', '56851', '56870', '56900', '56864')], '56768', '56779')])
@pytest.mark.parametrize('first,last', [(False, False), (False, True), (True, False), (True, True)])
def test_sup_two_nonempty_u16_arms_independent_snapshots_and_leaf_errors(client, selector, frame, diagrams, field, pairs, wait, waitport, first, last):
    p = sup_payload() if selector == 0 else sparse_sup_payload()
    p['literal_inputs'][pairs[0][4]] = first; p['literal_inputs'][pairs[1][4]] = last
    response = post(client, 'saved_sup_event_53656', p); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['source_case_uid'] == '76431' and result['source_selector_terminal_uid'] == '76455'
    assert result['source_NewVal_terminal_uid'] == '53859' and result['selected_case_frame'] == frame
    assert result['source_sequence_actual_diagram_uids'] == diagrams
    calls = {row['node_uid']: row for row in result['leaf_observations']}
    assert [row['sequence_phase'] for row in result['leaf_observations']] == [0, 0, 1, 2, 2]
    assert len(result['local_assignments']) == 2
    for index, (read, write, writer, data, literal, ref, refport, handler, errorport, errorout) in enumerate(pairs):
        expected = list(p['local_reads'][read]); expected[field] = p['literal_inputs'][literal]
        assert result['local_assignments'][index]['node_uid'] == write
        assert result['local_assignments'][index]['value'] == calls[writer]['inputs'][data] == expected
        assert result['field_updates'][index]['raw_flattened_field_index'] == field
        assert result['field_updates'][index]['typed_position_path'] == [field]
        assert calls[writer]['inputs'][refport] == p['reference_bindings'][ref]['native_reference']
        assert calls[handler]['inputs'][errorport] == p['native_boundaries'][writer]['outputs'][errorout]
        assert result['local_assignments'][index]['explicit_paramIdx'] == 26
    assert result['local_assignments'][0]['value'] != result['local_assignments'][1]['value']
    assert calls[wait]['inputs'] == {waitport: 1000}
    assert result['native_default_policy_qualified'] is False


def test_sup_minimal_is_nonempty_and_inactive_keys_are_not_source_inputs(client):
    response = post(client, 'saved_sup_event_53656', minimal_sup_payload()); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '76439' and len(result['leaf_observations']) == 5 and len(result['local_assignments']) == 2
    p = sup_payload(); p['completed_sinks'] = ['86045', '53881']
    p['local_reads'].update({'56568': None, '56833': 'inactive'})
    p['literal_inputs'].update({'56550': None, '56817': 'inactive'})
    p['reference_bindings'].update({'56529': None, '56792': 'inactive'})
    p['native_boundaries'].update({uid: None for uid in ('56584', '56650', '56768', '56849', '56870')})
    response = post(client, 'saved_sup_event_53656', p); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['completed_sinks'] == p['completed_sinks']
    assert result['completion_observations_are_feasible_trace'] is False
    assert [row['node_uid'] for row in result['local_reads']] == ['53890', '86012']


def test_sup_u16_literal_carrier_ref_error_and_boundary_refusals(client):
    mutants = []
    for value in (False, True, -1, 2, 65535, 65536, 0.0, None, '0'):
        p = sup_payload(); p['new_value'] = value; mutants.append(p)
    for uid in ('53890', '86012'):
        for value in ([False] * 39, [False] * 41, [0] * 40):
            p = sup_payload(); p['local_reads'][uid] = value; mutants.append(p)
    for uid in ('79753', '86078'):
        p = sup_payload(); p['literal_inputs'][uid] = 0; mutants.append(p)
        p = sup_payload(); del p['literal_inputs'][uid]; mutants.append(p)
    p = sup_payload(); p['reference_bindings']['54139']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['53908']['outputs']['53930']['status'] = 0; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['86028']['outputs']['86039']['code'] = 2**31; mutants.append(p)
    p = sup_payload(); del p['unwired_inputs']['53918']; mutants.append(p)
    p = sup_payload(); p['unwired_inputs']['70699'] = 65536; mutants.append(p)
    for report in (['53908', '53908'], ['63056'], ['56584']):
        p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
    for p in mutants: assert post(client, 'saved_sup_event_53656', p).status_code == 400
    p = sup_payload(); p['unwired_inputs']['70685'] = {'bytes_hex': '00FF'}
    response = post(client, 'saved_sup_event_53656', p); assert response.status_code == 200
    assert response.get_json()['result']['leaf_observations'][1]['inputs']['70685'] == {'bytes_hex': '00FF'}
    p['unwired_inputs']['70685'] = {'bytes_hex': 'ff'}
    assert post(client, 'saved_sup_event_53656', p).status_code == 400


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_40079', acq_payload), ('saved_sup_event_53656', sup_payload)])
def test_exact_identity_and_no_execution_extension(client, operation, factory):
    for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
        p = factory(); p[key] = 'wrong'; assert post(client, operation, p).status_code == 400
    p = factory(); p['execute_native'] = True; assert post(client, operation, p).status_code == 400


def test_measured_request_cap_and_distinct_web_response_policy(client):
    p = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_53656', inputs=p), ensure_ascii=False, separators=(',', ':')).encode('utf8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200 and len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X' * 65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_53656","operation":"saved_sup_event_53656","inputs":{}}',
                b'{"operation":"saved_sup_event_53656","inputs":{"event_outputs":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False
