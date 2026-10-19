"""New source-specific shared kernels exposed as stateless web replay."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'legacy/xp_acq_agent/tests'))
from next_event_fixtures import acq_payload, sup_payload

client = helpers.client


def post(client, operation, payload):
    return client.post('/api/elyse/supervision/replay', json=dict(operation=operation, inputs=payload))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_22879 as acq, supervision_gain_event as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_22879, saved_sup_gain
    assert acq.replay_event is saved_acq_event_22879.replay_event
    assert acq.replay_saved_acq_event_22879 is saved_acq_event_22879.replay_saved_acq_event_22879
    assert sup.project_gain is saved_sup_gain.project_gain
    assert sup.replay_saved_sup_gain is saved_sup_gain.replay_saved_sup_gain


@pytest.mark.parametrize('operation,fixture', [('saved_acq_event_22879', acq_payload), ('saved_sup_gain', sup_payload)])
def test_source_results_inputs_preserved_and_no_native_execution(client, operation, fixture):
    payload = fixture()
    before = copy.deepcopy(payload)
    response = post(client, operation, payload)
    assert response.status_code == 200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status'] == 'NOT_EXECUTED'
    result = response.json['result']
    assert result['hardware_writes'] is False and result['whole_event_equivalence'] is False
    if operation == 'saved_sup_gain':
        assert result['projected_cluster'][4] == 8.98
        assert result['multiplied_value'] == 8.98 * 10.0
        assert result['completed_sinks'] == ['57358', '53628']
        assert result['writer_success_gates_local_assignments'] is False
    else:
        writes = {row['node_uid']: row['value'] for row in result['writes']}
        assert writes['23331'][4] is False and writes['23408'][4] is True
        assert (writes['24589'][14], writes['24589'][15], writes['24589'][17]) == (False, False, True)
        assert result['selected_body_completed'] is True
    assert payload == before


def test_false_acq_arm_does_not_read_other_boundaries(client):
    payload = acq_payload(False)
    for key in ('schedule', 'snapshots', 'leaf_returns', 'unwired_inputs', 'reference_binding'):
        payload[key] = None
    response = post(client, 'saved_acq_event_22879', payload)
    assert response.status_code == 200
    assert response.json['result']['writes'] == []
    assert response.json['result']['leaf_calls'] == []


@pytest.mark.parametrize('selector', [True, -1, 3, 65535, 1.0])
def test_sup_saved_u16_range_does_not_imply_default_policy(client, selector):
    assert post(client, 'saved_sup_gain', sup_payload(selector)).status_code == 400


@pytest.mark.parametrize('mutation', ['bad_length', 'nan', 'inf', 'wrong_frame', 'duplicate_completion'])
def test_sup_unqualified_shapes_and_native_domains_refused(client, mutation):
    payload = sup_payload()
    if mutation == 'bad_length': payload['local_reads']['57311'].pop()
    elif mutation == 'nan': payload['local_reads']['57311'][0] = float('nan')
    elif mutation == 'inf': payload['local_reads']['57311'][0] = float('inf')
    elif mutation == 'wrong_frame': payload['frame_uid'] = '56136'
    else: payload['completed_sinks'] = ['57296', '57296']
    assert post(client, 'saved_sup_gain', payload).status_code == 400


@pytest.mark.parametrize('mutation', ['early_write', 'missing_read', 'nonbool', 'missing_return', 'wrong_ref'])
def test_acq_dependencies_supplied_returns_and_source_identity_refused(client, mutation):
    payload = acq_payload()
    if mutation == 'early_write': payload['schedule'][0] = dict(kind='step', uid='23331')
    elif mutation == 'missing_read': payload['snapshots'].pop('25058')
    elif mutation == 'nonbool': payload['new_value'] = 1
    elif mutation == 'missing_return': payload['leaf_returns'].pop('25625')
    else: payload['reference_binding']['constant_uid'] = '34004'
    assert post(client, 'saved_acq_event_22879', payload).status_code == 400
