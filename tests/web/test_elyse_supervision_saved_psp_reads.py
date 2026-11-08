"""Flask uses shared pure read caller and supplied data regardless of fault."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent import saved_psp_reads as core
from DeviceServers.control.elyse_acq.vi_simulation import timeout_reads as modern

client=helpers.client


def payload():
    defaults,returns={},{}
    for uid,tag,bank,size,element in core.SITES:
        defaults[uid]=[False if element is bool else 1.0]*size
        returns[uid]=dict(data=[True if element is bool else 2.0]*size,error=dict(status=False,code=-17,source=uid))
    return dict(source_id='APP-00',uid='10115',frame_returned=True,defaults=defaults,returns=returns,
        stop_before=True,tcp_ed_before=True)


def post(client,data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_psp_reads',inputs=data))


def test_same_shared_core_and_order(client):
    assert modern.replay_saved_psp_reads is core.replay_saved_psp_reads
    result=post(client,payload()).get_json()['result']
    assert [c['node_uid'] for c in result['calls']]==[s[0] for s in core.SITES]
    assert result['stop_after'] is True and result['external_calls_executed'] is False


def test_fault_preserves_returned_data_and_clears_final_flags(client):
    data=payload()
    data['returns']['19950']['error']['status']=True
    data['returns']['22840']['error'].update(status=True,code=0)
    result=post(client,data).get_json()['result']
    assert next(a['data'] for a in result['data_assignments'] if a['bank']==36)==[True]*29
    assert result['fault_assignments']==[dict(bank=30,value=False),dict(bank=45,value=False)]


def test_later_supplied_return_can_clear_earlier_fault(client):
    data=payload()
    data['returns']['19950']['error']['status']=True
    result=post(client,data).get_json()['result']
    assert result['fault_assignments']==[] and result['stop_after'] is True


@pytest.mark.parametrize('change',[dict(uid='43'),dict(frame_returned=False),dict(stop_before=1)])
def test_invalid_frame_or_boolean_refuses(client,change):
    data=payload()
    data.update(change)
    assert post(client,data).status_code==400
