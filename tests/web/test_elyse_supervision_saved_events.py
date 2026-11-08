"""Web source-body replay keeps exact shared functions and inert boundaries."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'legacy/xp_acq_agent/tests'))
from saved_event_fixtures import acq_control_payload, sup_frequency_payload

client = helpers.client


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_control_event as acq, supervision_frequency_event as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_33620, saved_sup_frequency
    assert acq.replay_acq_control_event is saved_acq_event_33620.replay_event
    assert acq.replay_saved_acq_event_33620 is saved_acq_event_33620.replay_saved_acq_event_33620
    assert sup.project_frequency is saved_sup_frequency.project_frequency
    assert sup.replay_saved_sup_frequency is saved_sup_frequency.replay_saved_sup_frequency


@pytest.mark.parametrize('operation,fixture', [
    ('saved_acq_event_33620', acq_control_payload), ('saved_sup_frequency', sup_frequency_payload)])
def test_source_results_and_no_external_effects(client, operation, fixture):
    payload = fixture()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status'] == 'NOT_EXECUTED'
    value = response.json['result']
    assert value['hardware_writes'] is False
    assert value['whole_event_equivalence'] is False
    if operation == 'saved_sup_frequency':
        assert value['projected_cluster'][2] == 2.25
        assert value['projected_cluster'][3] == 4294967295.0
        assert value['projected_cluster'][32] == 4.0
        assert value['writer_success_gates_local_assignments'] is False
    else:
        writes = {row['node_uid']: row['value'] for row in value['writes']}
        calls = {row['node_uid']: row['input_ports'] for row in value['leaf_calls']}
        assert writes['33891'][12] is False and calls['34036']['34060'][12] is True
        assert calls['34076']['34106'] == payload['leaf_returns']['34036']['34047']
    assert payload == before


def test_false_acq_arm_skips_unselected_boundaries(client):
    payload = acq_control_payload(False)
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
        payload[key] = None
    response = post(client, 'saved_acq_event_33620', payload)
    assert response.status_code == 200
    assert response.json['result']['writes'] == []
    assert response.json['result']['leaf_calls'] == []


@pytest.mark.parametrize('mutation', ['bool_u32', 'bad_length', 'nan', 'inf', 'wrong_frame', 'duplicate_completion'])
def test_sup_unqualified_domains_refused(client, mutation):
    payload = sup_frequency_payload()
    if mutation == 'bool_u32': payload['event_returns']['70885']['71474'] = True
    elif mutation == 'bad_length': payload['local_reads']['60452'].pop()
    elif mutation == 'nan': payload['local_reads']['60452'][0] = float('nan')
    elif mutation == 'inf': payload['local_reads']['60452'][0] = float('inf')
    elif mutation == 'wrong_frame': payload['frame_uid'] = '70870'
    else: payload['completed_sinks'] = ['59714', '59714']
    assert post(client, 'saved_sup_frequency', payload).status_code == 400


@pytest.mark.parametrize('mutation', ['early_write', 'missing_read', 'bool_newval', 'missing_return', 'wrong_ref'])
def test_acq_unqualified_domains_refused(client, mutation):
    payload = acq_control_payload()
    if mutation == 'early_write': payload['schedule'][0] = dict(kind='step', uid='33723')
    elif mutation == 'missing_read': payload['snapshots'].pop('33958')
    elif mutation == 'bool_newval': payload['new_value'] = 1
    elif mutation == 'missing_return': payload['leaf_returns'].pop('34036')
    else: payload['reference_binding']['constant_uid'] = '70272'
    assert post(client, 'saved_acq_event_33620', payload).status_code == 400
