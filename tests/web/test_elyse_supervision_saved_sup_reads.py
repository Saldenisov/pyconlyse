"""Supervision source slices share core with3.4 and preserve supplied faults."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent import saved_sup_reads as core
from DeviceServers.control.elyse_acq.vi_simulation import supervision_reads as facade

client=helpers.client


def payload(independent=False):
    uids=(core.INDEPENDENT,) if independent else core.CHAIN
    return dict(source_id='APP-17',uid='51964' if independent else '13595',
        frames_returned=['49696'] if independent else ['14799','15121'],
        defaults={u:{'default':u} for u in uids},references={u:'opaque:'+u for u in uids},
        returns={u:dict(data={'returned':u},error=dict(status=True,code=0,source=u)) for u in uids})


def post(client,data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_sup_reads',inputs=data))


@pytest.mark.parametrize('independent',[False,True])
def test_source_slices_shared_and_inert(client,independent):
    assert facade.replay_saved_sup_reads is core.replay_saved_sup_reads
    result=post(client,payload(independent)).get_json()['result']
    assert result['external_calls_executed'] is False
    assert len(result['local_assignments'])==(1 if independent else 13)
    assert result['final_error'] is None if independent else result['final_error']['status'] is True


@pytest.mark.parametrize('change',[dict(source_id='APP-00'),dict(uid='5909'),dict(frames_returned=[])])
def test_invalid_source_or_partial_frames_refuses(client,change):
    data=payload();data.update(change)
    assert post(client,data).status_code==400
