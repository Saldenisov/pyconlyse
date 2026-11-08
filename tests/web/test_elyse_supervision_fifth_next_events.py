"""G66 source-bound body projections in inert web replay; native domains open."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'legacy/xp_acq_agent/tests'))
from fifth_next_event_fixtures import acq_payload, sup_payload

client = helpers.client


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_34191 as acq, supervision_event_38030 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_34191, saved_sup_event_38030
    assert acq.replay_event is saved_acq_event_34191.replay_event
    assert acq.replay_saved_acq_event_34191 is saved_acq_event_34191.replay_saved_acq_event_34191
    assert sup.project_event_38030 is saved_sup_event_38030.project_event_38030
    assert sup.replay_saved_sup_event_38030 is saved_sup_event_38030.replay_saved_sup_event_38030


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_34191', acq_payload), ('saved_sup_event_38030', sup_payload)])
def test_results_source_limits_and_input_preservation(client, operation, fixture):
    payload = fixture()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status'] == 'NOT_EXECUTED'
    result = response.json['result']
    assert result['whole_event_equivalence'] is False
    if operation == 'saved_sup_event_38030':
        assert result['hardware_execution'] is False and result['native_execution'] is False
        page = result['local_assignments']['45062']['data']
        assert page[21] == pytest.approx(payload['event_returns']['38049']['38074'][21] - .1)
        assert page[6] is False and page[7] is True
        assert result['writer_call']['data'][2] == page[21]
        assert result['returned_error'] == payload['native_returns']['44982']['45013']
        assert result['error_text_hex'] == result['error_prefix_hex'] + '00505350FF'
        assert result['native_error_selector_projection_qualified'] is False
        assert result['multi_request_mask_default_qualified'] is False
        assert result['writer_success_gates_local_assignment'] is False
    else:
        assert result['hardware_writes'] is False and result['external_calls_executed'] is False
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        assert writes['34383'] is True and writes['34333'][29] is True
        assert writes['35784'][13] is False
        assert (writes['35744'][42], writes['35744'][39]) == (False, True)
        assert result['selected_body_completed'] is True
        assert result['psp_delivery_qualified'] is False
    assert payload == before


def test_acq_false_arm_avoids_body_boundaries(client):
    payload = acq_payload(False)
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
        payload[key] = None
    response = post(client, 'saved_acq_event_34191', payload)
    assert response.status_code == 200
    assert response.json['result']['writes'] == []
    assert response.json['result']['leaf_calls'] == []


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_34191', acq_payload), ('saved_sup_event_38030', sup_payload)])
@pytest.mark.parametrize('mutation', ['wrong_version', 'missing_version', 'wrong_frame'])
def test_original_source_identity_required(client, operation, fixture, mutation):
    payload = fixture()
    if mutation == 'wrong_version': payload['source_version'] = '0' * 64
    elif mutation == 'missing_version': payload.pop('source_version')
    else: payload['frame_uid'] = '45123'
    assert post(client, operation, payload).status_code == 400


@pytest.mark.parametrize('mutation', ['page_length', 'graph_length', 'nan', 'out_of_bound', 'nonfloat',
                                     'composite_mask', 'selector_type', 'bytehex', 'completion_duplicate', 'completion_outside'])
def test_sup_explicit_domains_and_unresolved_default_refusals(client, mutation):
    payload = sup_payload()
    if mutation == 'page_length': payload['local_reads']['45088'].pop()
    elif mutation == 'graph_length': payload['local_reads']['45088'][3].pop()
    elif mutation == 'nan': payload['event_returns']['38049']['38074'][21] = float('nan')
    elif mutation == 'out_of_bound': payload['event_returns']['38049']['38074'][21] = float(2 ** 41)
    elif mutation == 'nonfloat': payload['event_returns']['38049']['38074'][21] = 31
    elif mutation == 'composite_mask': payload['event_returns']['38049']['38074'][7] = True
    elif mutation == 'selector_type': payload['error_case_selector'] = 1
    elif mutation == 'bytehex': payload['native_returns']['44982']['45013']['source_hex'] = 'FF0'
    elif mutation == 'completion_duplicate': payload['completed_sinks'] = ['44959', '44959']
    else: payload['completed_sinks'] = ['10163']
    assert post(client, 'saved_sup_event_38030', payload).status_code == 400


@pytest.mark.parametrize('mutation', ['early_stage', 'carrier_shape', 'nonbool', 'missing_return', 'wrong_ref'])
def test_acq_saved_dependencies_and_leaf_return_boundaries(client, mutation):
    payload = acq_payload()
    if mutation == 'early_stage': payload['schedule'][0] = dict(kind='stage_complete', uid='34284')
    elif mutation == 'carrier_shape': payload['snapshots']['34377'].pop()
    elif mutation == 'nonbool': payload['new_value'] = 1
    elif mutation == 'missing_return': payload['leaf_returns'].pop('52054')
    else: payload['reference_bindings']['35851']['constant_uid'] = '49483'
    assert post(client, 'saved_acq_event_34191', payload).status_code == 400


def test_sup_nonstatus_hypothetical_selector_and_completion_observations(client):
    payload = sup_payload()
    payload['native_returns']['44982']['45013'] = dict(status=False, code=-77, source_hex='00E9B0FF')
    response = post(client, 'saved_sup_event_38030', payload)
    assert response.status_code == 200
    result = response.json['result']
    assert result['returned_error']['status'] is False
    assert result['error_case_selector'] is True
    assert result['error_text_hex'].endswith('00E9B0FF')
    assert result['native_error_selector_projection_qualified'] is False
    assert result['completed_sinks'] == ['44959', '38326']
    assert result['completion_observation_semantics'] == 'caller_subset_in_reported_order_not_feasible_trace_or_prefix'


def test_sup_raw_missing_index_remains_absent_in_web_projection(client):
    payload = sup_payload()
    newval = payload['event_returns']['38049']['38074']
    for index in (7, 6, 20, 19):
        newval[index] = False
    newval[9], newval[8] = True, False
    payload['completed_sinks'] = None
    payload['error_case_selector'] = False
    response = post(client, 'saved_sup_event_38030', payload)
    assert response.status_code == 200
    result = response.json['result']
    assert result['field_updates'][0]['raw_flattened_field_index'] is None
    assert result['field_updates'][0]['typed_position_path'] == [0]
    assert result['local_assignments']['38203']['data'][:2] == [True, False]
