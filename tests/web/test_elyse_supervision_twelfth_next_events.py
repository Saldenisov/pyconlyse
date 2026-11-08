"""G73 source-specific stateless web replays; no configured provider access."""
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
from twelfth_next_event_fixtures import (
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
    app.config.update(TESTING=True, JWT_SECRET_KEY='G73-software-only-current-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_exact_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_37991 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_23880 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_37991, saved_sup_event_23880
    assert acq.replay_event is saved_acq_event_37991.replay_event
    assert acq.replay_saved_acq_event_37991 is saved_acq_event_37991.replay_saved_acq_event_37991
    assert sup.project_event_23880 is saved_sup_event_23880.project_event_23880
    assert sup.replay_saved_sup_event_23880 is saved_sup_event_23880.replay_saved_sup_event_23880


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_37991', acq_payload), ('saved_acq_event_37991', false_acq_payload),
    ('saved_acq_event_37991', inflight_acq_payload), ('saved_sup_event_23880', sup_payload),
    ('saved_sup_event_23880', minimal_sup_payload), ('saved_sup_event_23880', sparse_sup_payload)])
def test_six_frozen_examples_adapter_identity_and_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_37991 import replay_saved_acq_event_37991
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_23880 import replay_saved_sup_event_23880
    payload = factory(); before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_37991 if operation == 'saved_acq_event_37991' else replay_saved_sup_event_23880
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_direct_seven_stages_boolean_fields_and_independent_publication_read(client):
    payload = acq_payload()
    response = post(client, 'saved_acq_event_37991', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    writes = {row['node_uid']: row['value'] for row in result['writes']}
    expected = {}
    for uid, read, fields in (
        ('38100','38118',{3:True}), ('38173','38189',{3:False}),
        ('38251','38267',{2:True}), ('38311','38327',{2:False}),
        ('38519','38540',{17:False,14:True,12:False}), ('38546','38564',{4:False})):
        carrier = list(payload['snapshots'][read])
        for index, value in fields.items():
            carrier[index] = value
        expected[uid] = carrier
    expected['38124'] = True
    assert writes == expected
    assert result['completed_stages'] == ['38074','38157','38205','38235','38295','38483','38592']
    calls = {row['node_uid']: row['input_ports'] for row in result['leaf_calls']}
    assert calls['38642']['38656'] == payload['snapshots']['38636']
    assert calls['38642']['38656'] != writes['38546']
    assert calls['38642']['38644'] == payload['reference_bindings']['38610']['native_ref']
    assert calls['38659']['38689'] == payload['leaf_returns']['38642']['38653']
    for uid, value in (('38132',{'38137':150}), ('38223',{'38228':3000}),
                        ('38273',{'38278':150}), ('38628',{'38633':100})):
        assert calls[uid] == value
    assert result['scheduler_qualified'] is False and result['native_callee_equivalence'] is False


@pytest.mark.parametrize('uid', ['37359','38163','38301','38489','38509'])
@pytest.mark.parametrize('value', [True,0,None,'False',0.0])
def test_acq_frozen_false_literal_domain_refuses_expansion(client, uid, value):
    payload = acq_payload(); payload['literal_inputs'][uid] = value
    assert post(client, 'saved_acq_event_37991', payload).status_code == 400
    payload = acq_payload(); del payload['literal_inputs'][uid]
    assert post(client, 'saved_acq_event_37991', payload).status_code == 400


def test_acq_false_nonaccess_inflight_and_extra_field_binding_refusal(client):
    response = post(client, 'saved_acq_event_37991', false_acq_payload())
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '38045' and result['writes'] == result['leaf_calls'] == []
    payload = inflight_acq_payload()
    response = post(client, 'saved_acq_event_37991', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['pending_leaf_uids'] == ['38132'] and result['active_stage'] == '38074'
    assert result['selected_body_completed'] is False
    payload['schedule'].append(dict(kind='stage_complete', uid='38074'))
    assert post(client, 'saved_acq_event_37991', payload).status_code == 400
    payload = acq_payload(); payload['field_index_bindings'] = {}
    assert post(client, 'saved_acq_event_37991', payload).status_code == 400


@pytest.mark.parametrize('first', [False,True])
def test_sup_true_literal_hypothesis_direct_individual_callee_ports_and_local_assignments(client, first):
    payload = sup_payload(); payload['literal_inputs']['17326'] = first
    response = post(client, 'saved_sup_event_23880', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '25142'
    assert result['selector_literal_uid'] == '25668' and result['selector_literal_raw_hex'] == '0000'
    assert result['selector_literal_interpretation_is_hypothetical'] is True
    calls = {row['node_uid']: row['inputs'] for row in result['leaf_observations']}
    assert calls['17431']['17465'] is first
    assert calls['17431']['17475'] == 9600
    assert calls['17431']['17478'] == payload['literal_inputs']['17367']
    assert calls['17485']['17525'] == payload['local_reads']['31193']
    for uid, face, producer, output in (
        ('17485','17519','17431','17440'),('17485','17528','17431','17453'),
        ('17531','17558','17485','17491'),('17531','17571','17485','17500'),
        ('17574','17614','17531','17534'),('17574','17624','17531','17543'),
        ('17627','17654','17574','17577'),('17627','17663','17574','17587'),
        ('28756','28794','17627','17630')):
        assert calls[uid][face] == payload['native_boundaries'][producer]['outputs'][output]
    assert calls['17666'] == {'17677':50}
    assert [(r['node_uid'],r['explicit_paramIdx'],r['value']) for r in result['local_assignments']] == [
        ('34747',90,payload['native_boundaries']['17531']['outputs']['17540']),
        ('30337',89,payload['native_boundaries']['17574']['outputs']['17584'])]
    assert result['native_callee_equivalence_qualified'] is False
    assert result['native_coercion_qualified'] is False
    assert set(result['actual_absent_structures']) == {'Sequence','ForLoop','ErrorCase','nMux','VariantToData',
        'ArrayMaxMin','InRangeAndCoerce','PSP writer'}


@pytest.mark.parametrize('value', [0,65535])
def test_sup_bounded_supplied_u16_widening_does_not_qualify_native_coercion(client, value):
    payload = sup_payload(); payload['local_reads']['31193'] = value
    payload['native_boundaries']['17531']['outputs']['17540'] = -(2**31)
    response = post(client, 'saved_sup_event_23880', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['leaf_observations'][1]['inputs']['17525'] == value
    assert result['local_assignments'][0]['value'] == -(2**31)
    assert result['local_reads'][0]['native_coercion_qualified'] is False


def test_sup_false_unused_eventdata_and_hypothetical_completions(client):
    response = post(client, 'saved_sup_event_23880', minimal_sup_payload())
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '25108' and result['leaf_observations'] == result['local_assignments'] == []
    payload = sup_payload(); payload['completed_sinks'] = ['28756','17431','30337']
    response = post(client, 'saved_sup_event_23880', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['completed_sinks'] == payload['completed_sinks']
    assert result['completion_observations_are_feasible_trace'] is False
    assert result['completion_observations_prove_success'] is False


@pytest.mark.parametrize('value', [-1,65536,True,1.0])
def test_sup_local_u16_refusals(client, value):
    payload = sup_payload(); payload['local_reads']['31193'] = value
    assert post(client, 'saved_sup_event_23880', payload).status_code == 400


def test_sup_literal_unwired_error_completion_byte_and_open_boundary_refusals(client):
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_23880 import UNQUALIFIED_FLAGS
    for flag in UNQUALIFIED_FLAGS:
        payload = sup_payload(); payload['unqualified_boundaries'][flag] = True
        assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    for uid, value in (('25668',0),('17326',0),('17367',{'bytes_hex':'00'})):
        payload = sup_payload(); payload['literal_inputs'][uid] = value
        assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    for raw in ('0','ff','GG','AB'*4097):
        payload = sup_payload(); payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex':raw}
        assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    payload = sup_payload(); del payload['unwired_inputs']['17471']
    assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    payload = sup_payload(); payload['native_boundaries']['17431']['outputs']['17440']['status'] = 0
    assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    payload = sup_payload(); payload['completed_sinks'] = ['17668']
    assert post(client, 'saved_sup_event_23880', payload).status_code == 400
    payload = sup_payload(); payload['native_boundaries']['17574']['outputs']['17584'] = {'bytes_hex':'00FF'}
    response = post(client, 'saved_sup_event_23880', payload)
    assert response.status_code == 200
    assert response.get_json()['result']['local_assignments'][1]['value'] == {'bytes_hex':'00FF'}


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_37991',acq_payload),('saved_sup_event_23880',sup_payload)])
def test_exact_source_version_keys_and_no_execute_extension(client, operation, factory):
    for key in ('source_id','source_version','event_uid','frame_uid'):
        payload = factory(); payload[key] = 'wrong'
        assert post(client, operation, payload).status_code == 400
    payload = factory(); payload['execute_native'] = True
    assert post(client, operation, payload).status_code == 400


def test_request_cap_strict_json_and_distinct_web_response_policy(client):
    # Allowed explicit refs duplicate through source ports; signed cap is separate.
    payload = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_23880',inputs=payload),ensure_ascii=False,separators=(',',':')).encode('utf8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200 and len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X'*65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_23880","operation":"saved_sup_event_23880","inputs":{}}',
                b'{"operation":"saved_sup_event_23880","inputs":{"event_outputs":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False
