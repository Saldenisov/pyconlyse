"""G65 source-bound task/error and axis/gap facets in web software replay."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'legacy/xp_acq_agent/tests'))
from fourth_next_event_fixtures import acq_payload, sup_payload

client = helpers.client


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay',
                       json=dict(operation=operation, inputs=payload))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_45123 as acq, supervision_event_65050 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_45123, saved_sup_event_65050
    assert acq.replay_event is saved_acq_event_45123.replay_event
    assert acq.replay_saved_acq_event_45123 is saved_acq_event_45123.replay_saved_acq_event_45123
    assert sup.project_event_65050 is saved_sup_event_65050.project_event_65050
    assert sup.replay_saved_sup_event_65050 is saved_sup_event_65050.replay_saved_sup_event_65050


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_45123', acq_payload), ('saved_sup_event_65050', sup_payload)])
def test_source_results_and_inputs_preserved(client, operation, fixture):
    payload = fixture()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status'] == 'NOT_EXECUTED'
    result = response.json['result']
    assert result['whole_event_equivalence'] is False
    if operation == 'saved_sup_event_65050':
        assert result['hardware_execution'] is False and result['native_execution'] is False
        reads = payload['local_reads']
        assert result['projected_cluster'][2] == pytest.approx((reads['62327'] * .0979 + 5.0) - reads['62319'] * .049)
        assert result['projected_cluster'][3] == pytest.approx((reads['69089'] * -.0979 + 5.0) - reads['69067'] * .049)
        assert result['handler_call']['supplied_error_in'] == payload['native_returns']['88939']['88950']
        assert result['local_assignments']['88976']['data'] == result['projected_cluster']
        assert result['writer_success_gates_local_assignment'] is False
    else:
        assert result['hardware_writes'] is False and result['external_calls_executed'] is False
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        assert writes['45254'] is True
        assert writes['45339'][18] is False
        assert (writes['45312'][55], writes['45312'][52]) == (False, True)
        assert result['selected_body_completed'] is True
        assert result['native_task_reference_qualified'] is False
    assert payload == before


def test_false_acq_arm_does_not_read_body_boundaries(client):
    payload = acq_payload(False)
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
        payload[key] = None
    response = post(client, 'saved_acq_event_45123', payload)
    assert response.status_code == 200
    assert response.json['result']['writes'] == []
    assert response.json['result']['leaf_calls'] == []


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_45123', acq_payload), ('saved_sup_event_65050', sup_payload)])
@pytest.mark.parametrize('mutation', ['wrong_version', 'missing_version', 'wrong_frame'])
def test_exact_original_source_identity_required(client, operation, fixture, mutation):
    payload = fixture()
    if mutation == 'wrong_version': payload['source_version'] = '0' * 64
    elif mutation == 'missing_version': payload.pop('source_version')
    else: payload['frame_uid'] = '23449' if operation == 'saved_acq_event_45123' else '73301'
    assert post(client, operation, payload).status_code == 400


@pytest.mark.parametrize('mutation', ['wrong_length', 'nan', 'out_of_bound', 'nonfloat'])
def test_explicit_sup_replay_domain_required(client, mutation):
    payload = sup_payload()
    if mutation == 'wrong_length': payload['local_reads']['88920'].pop()
    elif mutation == 'nan': payload['local_reads']['62319'] = float('nan')
    elif mutation == 'out_of_bound': payload['local_reads']['62327'] = float(2 ** 41)
    else: payload['local_reads']['62327'] = 10
    assert post(client, 'saved_sup_event_65050', payload).status_code == 400


@pytest.mark.parametrize('mutation', ['early_stage', 'bad_task_shape', 'nonbool', 'missing_return', 'wrong_ref'])
def test_acq_saved_dependencies_and_leaf_boundaries_required(client, mutation):
    payload = acq_payload()
    if mutation == 'early_stage': payload['schedule'][0] = dict(kind='stage_complete', uid='45203')
    elif mutation == 'bad_task_shape': payload['snapshots']['50001'].pop()
    elif mutation == 'nonbool': payload['new_value'] = 1
    elif mutation == 'missing_return': payload['leaf_returns'].pop('52872')
    else: payload['reference_bindings']['45391']['constant_uid'] = '45409'
    assert post(client, 'saved_acq_event_45123', payload).status_code == 400
