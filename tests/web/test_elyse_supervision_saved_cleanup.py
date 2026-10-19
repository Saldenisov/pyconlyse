"""Web cleanup replay shares portable state machine; never closes a resource."""
from tests.web import test_elyse_supervision_saved_xnode as helpers
import pytest

client=helpers.client


def partial_payload():
    return dict(source_id='APP-00',uid='246',outer_joined=True,stop_before=True,
        psp_error_seed=dict(status=True,code=-17,source='explicit seed'),tpg_sessions=['one','two'],
        schedule=[dict(kind='stop_reset'),dict(kind='psp_close',index=0)],
        returned_errors=[dict(node_uid='536',iteration=0,error=dict(status=True,code=17,source='failed close return'))])


def post(client,data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_cleanup',inputs=data))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import final_cleanup as modern
    from legacy.xp_acq_agent.elyse_agent import saved_cleanup as portable
    assert modern.plan_cleanup_step is portable.plan_cleanup_step
    assert modern.commit_cleanup_step is portable.commit_cleanup_step
    assert modern.replay_saved_cleanup is portable.replay_saved_cleanup


def test_reset_is_independent_of_partial_close_errors(client):
    response=post(client,partial_payload())
    assert response.status_code==200
    output=response.json['result']['outputs']
    assert output['stop_after'] is False
    assert output['psp_error_after']['status'] is True
    assert output['frame_returned'] is False
    assert response.json['result']['resource_close_success_qualified'] is False
    assert response.json['execution_allowed'] is False


@pytest.mark.parametrize('field,value',[('outer_joined',False),('psp_error_seed',None),('stop_before',1)])
def test_missing_preconditions_or_seed_returns400(client,field,value):
    data=partial_payload()
    data[field]=value
    assert post(client,data).status_code==400


def test_unreturned_psp_node_is_not_default_success(client):
    data=partial_payload()
    data['returned_errors']=[]
    assert post(client,data).status_code==400
