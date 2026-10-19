"""Shared function identity and web boundary for saved SUP pure kernels."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

client=helpers.client


def payload(sid):
    if sid=='APP-19':
        return dict(source_id=sid,buffer_x=[[10,20],[30,40]],buffer_y=[[1],[3]],extracted_row=[7,8],
                    extracted_column=[9],integral_x=1001.0,integral_y=1000.0,average=2,iteration=3)
    return dict(source_id=sid,rows=[[True,False,True,False,True,0.0,1.0,True,False,True,False] for _ in range(11 if sid=='APP-21' else 9)],threshold=0.5)


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import saved_supervision_helpers as facade
    from legacy.xp_acq_agent.elyse_agent import saved_sup_helpers as core,saved_sup_replay as adapter
    assert facade.profile_xy is core.profile_xy
    assert facade.discrepancy_vdirecte is core.discrepancy_vdirecte
    assert facade.discrepancy_vdeviee is core.discrepancy_vdeviee
    assert facade.replay_saved_sup_helpers is adapter.replay_saved_sup_helpers


@pytest.mark.parametrize('sid',['APP-19','APP-21','APP-22'])
def test_saved_kernels_web(client,sid):
    response=client.post('/api/elyse/supervision/replay',json=dict(operation='saved_sup_helper',inputs=payload(sid)))
    assert response.status_code==200
    value=response.json['result']
    assert value['source_id']==sid and value['whole_VI_equivalence'] is False
    assert response.json['execution_allowed'] is False
    if sid=='APP-21':assert value['outputs']['rows'][2][2] is False
    if sid=='APP-19':assert value['outputs']['mean_x']==[8.5,14.0]


@pytest.mark.parametrize('change',['zero_average','seven_fields','bad_source','button_int'])
def test_unqualified_domains_refuse(client,change):
    data=payload('APP-19' if change=='zero_average' else 'APP-21')
    if change=='zero_average':data['average']=0
    elif change=='seven_fields':data['rows'][0]=data['rows'][0][:7]
    elif change=='bad_source':data['source_id']='APP-15'
    else:data['rows'][0][10]=1
    assert client.post('/api/elyse/supervision/replay',json=dict(operation='saved_sup_helper',inputs=data)).status_code==400
