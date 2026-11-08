"""G78 source-specific stateless web replays; no configured provider access."""
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
from seventeenth_next_event_fixtures import (
    acq_payload, false_acq_payload, inflight_acq_payload,
    sup_payload, minimal_sup_payload, sparse_sup_payload, oversized_sup_payload, acq_expected_writes)
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
    app.config.update(TESTING=True, JWT_SECRET_KEY='G78-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_42457 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_47072 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_42457, saved_sup_event_47072
    assert acq.replay_event is saved_acq_event_42457.replay_event
    assert acq.replay_saved_acq_event_42457 is saved_acq_event_42457.replay_saved_acq_event_42457
    assert sup.project_event_47072 is saved_sup_event_47072.project_event_47072
    assert sup.replay_saved_sup_event_47072 is saved_sup_event_47072.replay_saved_sup_event_47072


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_42457', acq_payload), ('saved_acq_event_42457', false_acq_payload),
    ('saved_acq_event_42457', inflight_acq_payload), ('saved_sup_event_47072', sup_payload),
    ('saved_sup_event_47072', minimal_sup_payload), ('saved_sup_event_47072', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_42457 import replay_saved_acq_event_42457
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_47072 import replay_saved_sup_event_47072
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_42457 if operation == 'saved_acq_event_42457' else replay_saved_sup_event_47072
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_seven_phases_independent_reads_and_fault_routing(client):
    p = acq_payload(); response = post(client, 'saved_acq_event_42457', p)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert {r['node_uid']: r['value'] for r in result['writes']} == acq_expected_writes(p)
    assert result['completed_stages'] == ['42539', '39882', '35750', '1926', '42901', '41314', '44333']
    calls = {r['node_uid']: r['input_ports'] for r in result['leaf_calls']}
    for uid, face, read in (('41020', '41034', '40872'), ('41037', '41051', '40979'),
                           ('39791', '39805', '39762'), ('43112', '43127', '43106'), ('31968', '31982', '31683')):
        assert calls[uid][face] == p['snapshots'][read]
    for uid, face, producer, output in (('41037', '41045', '41020', '41031'), ('40987', '41017', '41037', '41048'),
            ('43112', '43121', '39791', '39802'), ('31968', '31976', '43112', '43124'), ('31985', '32082', '31968', '31979')):
        assert calls[uid][face] == p['leaf_returns'][producer][output]
    assert calls['42649'] == {'42654': 1000} and calls['40868'] == {'40877': 200}
    assert calls['43112']['43127'] != acq_expected_writes(p)['43003']
    p = inflight_acq_payload(); response = post(client, 'saved_acq_event_42457', p)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['active_stage'] == '39882' and result['pending_leaf_uids'] == ['41020']
    assert result['completed_stages'] == ['42539'] and result['selected_body_completed'] is False
    p['schedule'].append({'kind': 'stage_complete', 'uid': '39882'})
    assert post(client, 'saved_acq_event_42457', p).status_code == 400


def test_acq_explicit_absent_fields_and_exact_literal_domain(client):
    assert post(client, 'saved_acq_event_42457', acq_payload()).status_code == 200
    mutants = []
    for face in ('42589', '51321'):
        for value in (False, None, -1, 1, 0.0):
            p = acq_payload(); p['field_index_bindings'][face] = value; mutants.append(p)
        p = acq_payload(); del p['field_index_bindings'][face]; mutants.append(p)
    for value in (7.25, -0.0, True, 0, None):
        p = acq_payload(); p['literal_inputs']['40767'] = value; mutants.append(p)
    p = acq_payload(); del p['literal_inputs']['40767']; mutants.append(p)
    for uid in ('31686', '42907', '42917', '42927', '42947', '42957'):
        for value in (True, 0, None):
            p = acq_payload(); p['literal_inputs'][uid] = value; mutants.append(p)
        p = acq_payload(); del p['literal_inputs'][uid]; mutants.append(p)
    p = acq_payload(); p['reference_bindings']['40910']['saved_uri'] += '/other'; mutants.append(p)
    p = acq_payload(); p['leaf_returns']['41020']['41031']['status'] = 0; mutants.append(p)
    p = acq_payload(); p['unwired_inputs']['41014'] = 65536; mutants.append(p)
    for p in mutants: assert post(client, 'saved_acq_event_42457', p).status_code == 400


def test_sup_nested_page_field_paths_independent_dps_and_bytes(client):
    p = sup_payload(); response = post(client, 'saved_sup_event_47072', p)
    assert response.status_code == 200
    result = response.get_json()['result']; updated = list(p['local_reads']['47137'])
    for source, target in ((4, 20), (3, 23), (12, 21)): updated[target] = p['new_value'][source]
    assert result['source_case_uid'] == '47154' and result['source_selector_terminal_uid'] == '47156'
    assert result['selected_case_frame'] == '47168'
    assert result['local_assignments'][0]['node_uid'] == '47186' and result['local_assignments'][0]['value'] == updated
    assert [(r['raw_flattened_field_index'], r['typed_position_path'], r['destination_raw_flattened_field_index'])
            for r in result['field_updates']] == [(11, [4], 20), (10, [3], 23), (19, [12], 21)]
    calls = {r['node_uid']: r for r in result['leaf_observations']}
    assert calls['32048']['inputs'] == {'32652': p['reference_bindings']['31390']['native_reference'],
        '32658': p['unwired_inputs']['32658'], '32664': updated}
    assert calls['28270']['inputs'] == {'28277': p['event_time_40518']}
    case = result['case_observations'][0]
    assert (case['node_uid'], case['selector_terminal_uid'], case['selected_frame']) == ('19594', '36566', '36477')
    expected_hex = p['literal_inputs']['35281']['bytes_hex'] + p['native_boundaries']['32048']['outputs']['32661']['source_hex']
    assert result['local_assignments'][1]['value'] == {'bytes_hex': expected_hex}
    assert result['completed_sinks'] == ['40558', '32048']
    assert result['completion_observations_are_feasible_trace'] is False


def test_sup_busy_only_wait_nonaccess_and_hypothetical_error_selector(client):
    for index in range(29):
        p = minimal_sup_payload(); p['local_reads']['47137'] = [False] * 29; p['local_reads']['47137'][index] = True
        p['new_value'] = {'not_a_Page': 1}; p['reference_bindings'] = None; p['unwired_inputs'] = None
        p['intrinsic_inputs'] = None; p['event_time_40518'] = None
        p['literal_inputs']['35281'] = None; p['native_boundaries']['32048'] = 'unused'
        p['literal_inputs']['42462'] = 4294967295
        response = post(client, 'saved_sup_event_47072', p); assert response.status_code == 200
        result = response.get_json()['result']
        assert result['selected_case_frame'] == '47226' and result['local_assignments'] == []
        assert [r['node_uid'] for r in result['leaf_observations']] == ['28270']
        assert result['source_Wait_input_value'] == 4294967295
    for status in (False, True):
        for selector in (False, True):
            p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['status'] = status
            p['intrinsic_inputs']['19594'] = selector; p['completed_sinks'] = ['28270', '47186']
            response = post(client, 'saved_sup_event_47072', p); assert response.status_code == 200
            result = response.get_json()['result']
            assert len(result['local_assignments']) == (2 if selector else 1)
            assert result['native_ErrorCluster_Case_selection_qualified'] is False
    response = post(client, 'saved_sup_event_47072', sparse_sup_payload()); assert response.status_code == 200
    result = response.get_json()['result']
    assert result['case_observations'][0]['selected_frame'] == '36498'
    assert result['decoded_literal_observations'] == [] and result['source_Wait_input_value'] == 17


def test_sup_active_carrier_literal_reference_error_and_boundary_refusals(client):
    mutants = []
    for value in (-1, 4294967296, True, 0.0, None):
        p = sup_payload(); p['event_time_40518'] = value; mutants.append(p)
        p = minimal_sup_payload(); p['literal_inputs']['42462'] = value; mutants.append(p)
    for value in ([False] * 28, [False] * 30, [0] * 29):
        p = sup_payload(); p['local_reads']['47137'] = value; mutants.append(p)
    for value in (0, None, 'True'):
        p = sup_payload(); p['intrinsic_inputs']['19594'] = value; mutants.append(p)
    for index, value in ((4, 0), (1, 65536), (0, [0.0] * 6), (10, {'bytes_hex': 'ff'})):
        p = sup_payload(); p['new_value'][index] = value; mutants.append(p)
    p = sup_payload(); p['reference_bindings']['31390']['stored_URI_bytes']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['literal_inputs']['35281']['bytes_hex'] += '00'; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['status'] = 0; mutants.append(p)
    p = sup_payload(); p['native_boundaries']['32048']['outputs']['32661']['code'] = 2**31; mutants.append(p)
    p = sup_payload(); del p['unwired_inputs']['32658']; mutants.append(p)
    for report in (['32048', '32048'], ['47154']):
        p = sup_payload(); p['completed_sinks'] = report; mutants.append(p)
    for flag in sup_payload()['unqualified_boundaries']:
        p = sup_payload(); p['unqualified_boundaries'][flag] = True; mutants.append(p)
    for p in mutants: assert post(client, 'saved_sup_event_47072', p).status_code == 400


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_42457', acq_payload), ('saved_sup_event_47072', sup_payload)])
def test_exact_identity_and_no_execution_extension(client, operation, factory):
    for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
        p = factory(); p[key] = 'wrong'; assert post(client, operation, p).status_code == 400
    p = factory(); p['execute_native'] = True; assert post(client, operation, p).status_code == 400


def test_measured_request_cap_and_distinct_web_response_policy(client):
    p = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_47072', inputs=p), ensure_ascii=False, separators=(',', ':')).encode('utf8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200 and len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X' * 65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_47072","operation":"saved_sup_event_47072","inputs":{}}',
                b'{"operation":"saved_sup_event_47072","inputs":{"event_outputs":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False
