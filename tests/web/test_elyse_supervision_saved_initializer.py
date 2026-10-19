"""Web replay calls shared portable caller-routing body."""
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent.saved_initializer import STAGES
import pytest

client=helpers.client


def payload():
    return dict(source_id='APP-00',uid='227',fixtures=[
        dict(tasks=['supplied:{0}:{1}'.format(i,j) for j in range(sum(n for b,n in stage[4]))],
             error_out=dict(status=i==1,code=-200284,source='explicit external return'))
        for i,stage in enumerate(STAGES)],
        clear_returns={'1532':dict(status=True,code=17,source='explicit external return')})


def post(client,data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_initializer',inputs=data))


def test_shared_route_identity():
    from DeviceServers.control.elyse_acq.vi_simulation import initialization_caller as modern
    from legacy.xp_acq_agent.elyse_agent import saved_initializer as portable
    assert modern.route_initializer_values is portable.route_initializer_values
    assert modern.route_ai_test_values is portable.route_ai_test_values
    assert modern.replay_saved_initializer is portable.replay_saved_initializer


def test_explicit_failed_clear_reaches_next_initializer(client):
    response=post(client,payload())
    assert response.status_code==200
    result=response.json['result']
    assert [s['node_uid'] for s in result['steps']]==['593','262','1532','500','620']
    assert result['steps'][3]['error_in']['status'] is True
    assert result['reference_validity_qualified'] is False
    assert response.json['execution_allowed'] is False


@pytest.mark.parametrize('uid,clears',[('unknown',{}),('227',{}),('227',{'1532':dict(status=1,code=0,source='')})])
def test_unknown_frame_missing_return_or_invalid_status_returns400(client,uid,clears):
    data=payload()
    data.update(uid=uid,clear_returns=clears)
    assert post(client,data).status_code==400


def test_original_fallback_error_remains_separate(client):
    raw=dict(status=True,code=-200284,source='read')
    clear=dict(status=False,code=17,source='clear')
    data=dict(source_id='APP-00',uid='133',read_error=raw,
         fallback_result=dict(tasks=['new-one','new-two'],error_out=dict(status=False,code=99,source='retry')),
         clear_returns={uid:clear for uid in ('2134','4034','7931')})
    response=post(client,data)
    assert response.status_code==200
    assert response.json['result']['outputs']['original_read_error']==raw
    assert response.json['result']['outputs']['sequence_local_306']['source']=='retry'
