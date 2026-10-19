"""G68 web uses identical pure kernels; property/serializer/loop claims stay open."""
import copy
from pathlib import Path
import sys
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'legacy/xp_acq_agent/tests'))
from seventh_next_event_fixtures import acq_payload,sup_payload

client=helpers.client


def post(client,operation,payload):
    return client.post('/api/elyse/supervision/replay',json=dict(operation=operation,inputs=payload))


def test_shared_kernel_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import acquisition_event_31552 as acq,supervision_event_18780 as sup
    from legacy.xp_acq_agent.elyse_agent import saved_acq_event_31552,saved_sup_event_18780
    assert acq.replay_event is saved_acq_event_31552.replay_event
    assert acq.replay_saved_acq_event_31552 is saved_acq_event_31552.replay_saved_acq_event_31552
    assert sup.project_event_18780 is saved_sup_event_18780.project_event_18780
    assert sup.replay_saved_sup_event_18780 is saved_sup_event_18780.replay_saved_sup_event_18780


@pytest.mark.parametrize('operation,fixture',[
    ('saved_acq_event_31552',acq_payload),('saved_sup_event_18780',sup_payload)])
def test_actual_body_and_unchanged_envelope(client,operation,fixture):
    payload=fixture();before=copy.deepcopy(payload)
    response=post(client,operation,payload)
    assert response.status_code==200
    assert response.json['execution_allowed'] is False
    assert response.json['physical_status']=='NOT_EXECUTED'
    r=response.json['result']
    assert r['whole_event_equivalence'] is False
    if operation=='saved_acq_event_31552':
        writes={x['node_uid']:x['value'] for x in r['writes']}
        assert writes['33041'][20] is True and writes['33185'][20] is False
        calls={x['node_uid']:x['input_ports'] for x in r['leaf_calls']}
        assert calls['33144']['33149']==150 and calls['33985']['34152']==100
        assert r['snapshot_equality_qualified'] is False
    else:
        assert r['iteration_count']==33
        assert [x['index'] for x in r['iterations'] if x['changed']]==[0,7,32]
        assert r['loop_error_candidate']!=r['supplied_loop_error_output']
        for flag in ('native_loop_output_policy_qualified','native_formatting_qualified',
                     'native_variant_conversion_qualified','native_literal_storage_decode_qualified',
                     'control_reference_constants_are_local_bank_reads'):
            assert r[flag] is False
    assert payload==before


def test_false_arm_no_boundary_access(client):
    p=acq_payload(False)
    for key in ('schedule','snapshots','leaf_returns','unwired_inputs','reference_bindings'):p[key]=None
    r=post(client,'saved_acq_event_31552',p)
    assert r.status_code==200 and r.json['result']['leaf_calls']==[]


@pytest.mark.parametrize('operation,fixture',[
    ('saved_acq_event_31552',acq_payload),('saved_sup_event_18780',sup_payload)])
@pytest.mark.parametrize('mutation',['wrong_version','missing_version','wrong_frame'])
def test_exact_original_identity(client,operation,fixture,mutation):
    p=fixture()
    if mutation=='wrong_version':p['source_version']='0'*64
    elif mutation=='missing_version':p.pop('source_version')
    else:p['frame_uid']='43634'
    assert post(client,operation,p).status_code==400


@pytest.mark.parametrize('mutation',['shape','missing_loop_error','missing_literal','reference_index','selector','completion'])
def test_sup_unknown_boundary_refusals(client,mutation):
    p=sup_payload()
    if mutation=='shape':p['event_returns']['19499']['19678'].pop()
    elif mutation=='missing_loop_error':p['intrinsic_outputs'].pop('29296')
    elif mutation=='missing_literal':p['literal_inputs'].pop('47580')
    elif mutation=='reference_index':p['local_reads']['8733']=33
    elif mutation=='selector':p['intrinsic_outputs']['20154']=1
    else:p['completed_sinks']=[['20132',1]]
    assert post(client,'saved_sup_event_18780',p).status_code==400


def test_sup_caller_pair_order_and_storage_hypothesis(client):
    p=sup_payload();p['literal_inputs']['47580']=19.0
    p['completed_sinks']=[['20132',32],['20132',0]]
    r=post(client,'saved_sup_event_18780',p)
    assert r.status_code==200
    result=r.json['result']
    assert result['literal_observations']['47580']==19.0
    assert result['completed_sinks']==p['completed_sinks']
    assert 'not_source_feasible_schedule_or_prefix' in result['completion_observation_semantics']
