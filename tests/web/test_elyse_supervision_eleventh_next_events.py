"""G72 fresh source-specific web routes; configured providers remain inaccessible."""
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
from eleventh_next_event_fixtures import (
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
    app.config.update(TESTING=True, JWT_SECRET_KEY='G72-software-only-source-web-key')
    JWTManager(app)
    app.register_blueprint(api.elyse_supervision_api)
    return app.test_client()


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_shared_core_facade_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_38732 as acq
    from DeviceServers.control.elyse_acq.vi_simulation import supervision_event_26490 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_38732, saved_sup_event_26490
    assert acq.replay_event is saved_acq_event_38732.replay_event
    assert acq.replay_saved_acq_event_38732 is saved_acq_event_38732.replay_saved_acq_event_38732
    assert sup.project_event_26490 is saved_sup_event_26490.project_event_26490
    assert sup.replay_saved_sup_event_26490 is saved_sup_event_26490.replay_saved_sup_event_26490


@pytest.mark.parametrize('operation,factory', [
    ('saved_acq_event_38732', acq_payload), ('saved_acq_event_38732', false_acq_payload),
    ('saved_acq_event_38732', inflight_acq_payload), ('saved_sup_event_26490', sup_payload),
    ('saved_sup_event_26490', minimal_sup_payload), ('saved_sup_event_26490', sparse_sup_payload)])
def test_six_exact_examples_same_adapter_safe_envelope(client, operation, factory):
    from legacy.xp_acq_agent.elyse_agent.saved_acq_event_38732 import replay_saved_acq_event_38732
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_26490 import replay_saved_sup_event_26490
    payload = factory()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    body = response.get_json()
    assert body['execution_allowed'] is False and body['physical_status'] == 'NOT_EXECUTED'
    assert body['input_origin'] == 'OPERATOR_SUPPLIED_REPLAY'
    adapter = replay_saved_acq_event_38732 if operation == 'saved_acq_event_38732' else replay_saved_sup_event_26490
    assert body['result'] == adapter(payload) and payload == before
    assert tuple(body['result'][k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid')) == tuple(
        payload[k] for k in ('source_id', 'source_version', 'event_uid', 'frame_uid'))
    assert body['result']['whole_event_equivalence'] is False


def test_acq_six_flat_phases_fields_fresh_snapshots_and_supplied_error_routes(client):
    payload = acq_payload()
    response = post(client, 'saved_acq_event_38732', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    writes = {r['node_uid']: r['value'] for r in result['writes']}
    first = [0.0] * 10
    first[8] = payload['snapshots']['38883'][8]
    second = [0.0] * 10
    for i in (2, 5):
        second[i] = payload['snapshots']['38959'][i]
    assert writes['38841'] == first and writes['38897'] == second and writes['38889'] is True
    assert result['completed_stages'] == ['38812', '38987', '39227', '39387', '39743', '39965']
    calls = {r['node_uid']: r['input_ports'] for r in result['leaf_calls']}
    for uid, face, read in (('39140', '39158', '39043'), ('39162', '39180', '39059'),
                            ('39861', '39875', '39855'), ('39885', '39901', '39878')):
        assert calls[uid][face] == payload['snapshots'][read]
    assert calls['39140']['39158'] != writes['38841']
    for uid, face, producer, output in (('39162', '39171', '39140', '39153'),
                                       ('39076', '39134', '39162', '39176'),
                                       ('39885', '39895', '39861', '39872'),
                                       ('39904', '39934', '39885', '39898')):
        assert calls[uid][face] == payload['leaf_returns'][producer][output]
        assert calls[uid][face]['status'] is True
    assert calls['39266'] == {'39273': 1000} and calls['39983'] == {'39988': 200}
    assert result['scheduler_qualified'] is False and result['native_runtime_equivalence'] is False


def test_acq_false_nonaccess_inflight_and_explicit_index_refusals(client):
    payload = false_acq_payload()
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings',
                'field_index_bindings', 'literal_inputs'):
        payload[key] = None
    response = post(client, 'saved_acq_event_38732', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['selected_case_frame'] == '38786' and result['writes'] == result['leaf_calls'] == []
    payload = inflight_acq_payload()
    response = post(client, 'saved_acq_event_38732', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['pending_leaf_uids'] == ['39140'] and result['active_stage'] == '38987'
    assert result['selected_body_completed'] is False
    payload['schedule'].append(dict(kind='stage_complete', uid='38987'))
    assert post(client, 'saved_acq_event_38732', payload).status_code == 400
    for face in ('38855', '38911'):
        payload = acq_payload()
        del payload['field_index_bindings'][face]
        assert post(client, 'saved_acq_event_38732', payload).status_code == 400


@pytest.mark.parametrize('first,last', [(False, False), (False, True), (True, False), (True, True)])
def test_sup_direct_source_sequence_literal_hypotheses_and_same_local_alias(client, first, last):
    payload = sup_payload()
    payload['literal_inputs'] = {'20659': first, '21637': last}
    payload['completed_sinks'] = ['21619', '19732']
    response = post(client, 'saved_sup_event_26490', payload)
    assert response.status_code == 200
    result = response.get_json()['result']
    assert result['source_sequence_uid'] == '20194'
    assert result['source_phase_order'] == ['20201', '21020', '21238']
    rows = result['source_assignments']
    assert [(r['node_uid'], r['value'], r['source_literal_raw_hex'], r['source_diagram_uid']) for r in rows] == [
        ('19732', first, '01', '20206'), ('21619', last, '0000', '21245')]
    assert all((r['explicit_paramIdx'], r['saved_FP_bank_uid'], r['control_terminal_uid']) == (132, '19944', '19961') for r in rows)
    assert all(r['decoded_literal_is_hypothetical'] is True for r in rows)
    wait = result['wait_observation']
    assert (wait['node_uid'], wait['source_diagram_uid'], wait['provided_data_U32_input'],
            wait['unused_output_terminal_uid']) == ('22081', '21027', 200, '22087')
    assert wait['supplied_unused_return'] == payload['wait_return']
    assert result['supplied_unused_event_outputs'] == payload['event_outputs']
    assert result['completed_sinks'] == ['21619', '19732']
    assert result['completion_observations_are_feasible_trace'] is False
    assert result['completion_observations_prove_success'] is False
    assert result['native_storage_serializer_qualified'] is False
    assert set(result['actual_absent_structures']) == {'Case', 'ForLoop', 'ErrorCase', 'nMux',
                                                    'VariantToData', 'ArrayMaxMin', 'InRangeAndCoerce', 'PSP writer'}


def test_sup_explicit_storage_completion_and_boundary_refusals(client):
    from legacy.xp_acq_agent.elyse_agent.saved_sup_event_26490 import QUALIFICATION_FLAGS
    for uid in ('20659', '21637'):
        payload = sup_payload()
        payload['literal_inputs'][uid] = 0
        assert post(client, 'saved_sup_event_26490', payload).status_code == 400
    for flag in QUALIFICATION_FLAGS:
        payload = sup_payload()
        payload['unqualified_boundaries'][flag] = True
        assert post(client, 'saved_sup_event_26490', payload).status_code == 400
    payload = sup_payload()
    payload['completed_sinks'] = ['22087']
    assert post(client, 'saved_sup_event_26490', payload).status_code == 400
    payload = sup_payload()
    payload['wait_return'] = 'X' * 4097
    assert post(client, 'saved_sup_event_26490', payload).status_code == 400


@pytest.mark.parametrize('operation,factory', [('saved_acq_event_38732', acq_payload),
                                              ('saved_sup_event_26490', sup_payload)])
def test_exact_source_version_and_no_execute_extension(client, operation, factory):
    for key in ('source_id', 'source_version', 'event_uid', 'frame_uid'):
        payload = factory()
        payload[key] = 'wrong'
        assert post(client, operation, payload).status_code == 400
    payload = factory()
    payload['execute_native'] = True
    assert post(client, operation, payload).status_code == 400


def test_request_cap_strict_json_and_web_output_policy(client):
    # Web accepts this pure result; the signed RPC response applies its own cap.
    payload = oversized_sup_payload()
    raw = json.dumps(dict(operation='saved_sup_event_26490', inputs=payload),
                     ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    assert len(raw) <= 65536
    response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
    assert response.status_code == 200
    assert len(response.data) > 65536
    assert response.get_json()['execution_allowed'] is False
    response = client.post('/api/elyse/supervision/replay', data=b'X' * 65537, content_type='application/json')
    assert response.status_code == 413 and response.get_json()['error'] == 'Replay body exceeds 65536 bytes'
    for raw in (b'{"operation":"saved_sup_event_26490","operation":"saved_sup_event_26490","inputs":{}}',
                b'{"operation":"saved_sup_event_26490","inputs":{"wait_return":NaN}}'):
        response = client.post('/api/elyse/supervision/replay', data=raw, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['execution_allowed'] is False


@pytest.mark.parametrize('uid,value',
    [('38829', value) for value in (7.25, -0.0, 0, None, False, '0.0')] +
    [(uid, value) for uid in ('39475', '39502', '42005') for value in (True, 0, None, 'False', 0.0)])
def test_acq_bounded_literal_projection_refusals(client, uid, value):
    payload = acq_payload()
    payload['literal_inputs'][uid] = value
    assert post(client, 'saved_acq_event_38732', payload).status_code == 400
    payload = acq_payload()
    del payload['literal_inputs'][uid]
    assert post(client, 'saved_acq_event_38732', payload).status_code == 400
