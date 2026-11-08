"""Inert G67 web route to same stdlib body; source/native boundaries stay open."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'legacy/xp_acq_agent/tests'))
from sixth_next_event_fixtures import acq_payload, sup_payload

client = helpers.client


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_43634 as acq, supervision_event_53716 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_43634, saved_sup_event_53716
    assert acq.replay_event is saved_acq_event_43634.replay_event
    assert acq.replay_saved_acq_event_43634 is saved_acq_event_43634.replay_saved_acq_event_43634
    assert sup.project_event_53716 is saved_sup_event_53716.project_event_53716
    assert sup.replay_saved_sup_event_53716 is saved_sup_event_53716.replay_saved_sup_event_53716


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_43634', acq_payload), ('saved_sup_event_53716', sup_payload)])
def test_exact_body_results_and_open_domains(client, operation, fixture):
    payload = fixture()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status'] == 'NOT_EXECUTED'
    result = response.json['result']
    assert result['whole_event_equivalence'] is False
    if operation == 'saved_acq_event_43634':
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        assert writes['43738'][29] is False and writes['43763'] is True
        assert writes['43848'][14] is False
        assert (writes['43821'][42], writes['43821'][39]) == (True, False)
        assert result['psp_delivery_qualified'] is False
    else:
        assert result['arithmetic_by_uid']['51397']['value'] == 11.0
        assert result['range_by_uid']['52918']['value'] == 11.0
        assert result['local_assignments']['53024']['data'][5] == 11.0
        assert result['writer_call']['data'][4] == 11.0
        assert result['range_by_uid']['52918']['unused_boolean_output_evaluated'] is False
        assert result['native_literal_storage_decode_qualified'] is False
        assert result['native_primitive_semantics_qualified'] is False
        assert result['native_error_selector_projection_qualified'] is False
        assert result['writer_success_gates_local_assignment'] is False
    assert payload == before


def test_false_acq_arm_does_not_access_body_boundaries(client):
    payload = acq_payload(False)
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_bindings'):
        payload[key] = None
    response = post(client, 'saved_acq_event_43634', payload)
    assert response.status_code == 200
    assert response.json['result']['writes'] == []
    assert response.json['result']['leaf_calls'] == []


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_43634', acq_payload), ('saved_sup_event_53716', sup_payload)])
@pytest.mark.parametrize('mutation', ['wrong_version', 'missing_version', 'wrong_frame'])
def test_exact_source_version_required(client, operation, fixture, mutation):
    payload = fixture()
    if mutation == 'wrong_version': payload['source_version'] = '0' * 64
    elif mutation == 'missing_version': payload.pop('source_version')
    else: payload['frame_uid'] = '34191'
    assert post(client, operation, payload).status_code == 400


@pytest.mark.parametrize('mutation', ['lower_endpoint', 'upper_endpoint', 'outside', 'reversed',
    'composite', 'literal_type', 'selector', 'completion', 'shape', 'nan'])
def test_sup_storage_and_range_mode_domains_refuse(client, mutation):
    payload = sup_payload()
    values = payload['event_returns']['53735']['53762']
    if mutation == 'lower_endpoint': values[5] = -1.0
    elif mutation == 'upper_endpoint': values[5] = 19.0
    elif mutation == 'outside': values[5] = 20.0
    elif mutation == 'reversed': payload['literal_inputs']['58402'] = 21.0
    elif mutation == 'composite': values[2] = True
    elif mutation == 'literal_type': payload['literal_inputs']['58402'] = 0
    elif mutation == 'selector': payload['error_case_selector'] = 1
    elif mutation == 'completion': payload['completed_sinks'] = ['53024', '53024']
    elif mutation == 'shape': values.pop()
    else: values[5] = float('nan')
    assert post(client, 'saved_sup_event_53716', payload).status_code == 400


def test_sup_supplied_lower_is_hypothetical_and_not_native_storage(client):
    payload = sup_payload()
    payload['literal_inputs']['58402'] = 2.0
    result = post(client, 'saved_sup_event_53716', payload).json['result']
    assert result['range_by_uid']['52918']['input_slots']['2'] == 2.0
    assert result['supplied_literal_observations'] == {'58402': 2.0}
    assert 'hypothetical' in result['supplied_literal_semantics']
    assert result['completion_observation_semantics'] == 'caller_subset_in_reported_order_not_feasible_trace_or_prefix'


def test_sup_dps_busy_branch_uses_supplied_byte_prefix_without_wait(client):
    payload = sup_payload()
    for i in (2, 4, 3, 1, 14, 16, 15, 13):
        payload['event_returns']['53735']['53762'][i] = False
    payload['local_reads']['53769'][22] = True
    payload['literal_inputs']['55804'] = 'E9B0'
    payload['literal_inputs']['55821'] = dict(status=False, code=-37, source_hex='00FF')
    payload['completed_sinks'] = None
    result = post(client, 'saved_sup_event_53716', payload).json['result']
    assert result['writer_call'] is None and result['wait_call'] is None
    assert result['error_text_hex'] == 'E9B000FF'
    assert result['returned_error'] == payload['literal_inputs']['55821']
    assert result['native_literal_storage_decode_qualified'] is False
