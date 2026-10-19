"""Web andmodern facade use the same source-qualified portable functions."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers

client=helpers.client


def payload(sid):
    count=136 if sid=='APP-02' else 12
    values=[dict(task='r'+str(i),error=dict(status=i==11,code=i,source='supplied')) for i in range(count)]
    if sid=='APP-02':values.append(dict(status=True,code=99,source='ignored handler'))
    data=dict(source_id=sid,returns=values,error_in=dict(status=True,code=17,source='input'))
    if sid!='APP-01':data.update(rate_hz=5000.0,samples_per_channel=10,public_error_seed=None)
    if sid=='APP-02':data.update(trigger_c1='/1/PFI0',trigger_c2='/2/PFI0')
    return data


def test_facade_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import saved_card_initializers as modern
    from legacy.xp_acq_agent.elyse_agent import saved_card_init,saved_card_replay
    assert modern.project_dio96 is saved_card_init.project_dio96
    assert modern.project_ni6071e is saved_card_init.project_ni6071e
    assert modern.project_ni6259 is saved_card_init.project_ni6259
    assert modern.replay_saved_card_init is saved_card_replay.replay_saved_card_init


@pytest.mark.parametrize('sid,tasks',[('APP-01',['r1','r3','r5','r7','r9','r11']),('APP-02',['r67','r135']),('APP-04',['r11'])])
def test_web_saved_card_bodies(client,sid,tasks):
    response=client.post('/api/elyse/supervision/replay',json=dict(operation='saved_card_init',inputs=payload(sid)))
    assert response.status_code==200
    assert response.json['result']['outputs']['tasks']==tasks
    assert response.json['execution_allowed'] is False
    assert response.json['result']['whole_VI_equivalence'] is False


@pytest.mark.parametrize('field,value',[('source_id','APP-03'),('returns',[]),('rate_hz',5000),('samples_per_channel',-1)])
def test_web_refuses_unqualified_representation(client,field,value):
    data=payload('APP-02');data[field]=value
    assert client.post('/api/elyse/supervision/replay',json=dict(operation='saved_card_init',inputs=data)).status_code==400
