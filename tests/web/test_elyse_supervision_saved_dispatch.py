"""Saved dispatch retains default ACTION and distinct publication snapshots."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent import saved_dispatch as core
from DeviceServers.control.elyse_acq import dps_bridge

client=helpers.client


def payload():
    return dict(source_id='APP-00',uid='8105',facet='dispatch',dps=[False]*29,event_index=None)


def post(client,data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_dispatch',inputs=data))


def test_same_core_and_orphan_property_target(client):
    assert dps_bridge.replay_saved_dispatch is core.replay_saved_dispatch
    data=payload()
    data['dps'][22]=True
    result=post(client,data).get_json()['result']
    assert result['outputs']['registered_event'] is None
    assert result['outputs']['property_assignments']==[['Value',True],['Val(Sgnl)',True]]
    assert result['external_calls_executed'] is False


def test_tail_default_writes_action_without_property_or_event(client):
    data=payload()
    data['dps'][28]=True
    result=post(client,data).get_json()['result']
    assert result['outputs']['state']=='SAVED_DEFAULT'
    assert result['outputs']['case_selector']==29
    assert result['outputs']['action_assignment'] is False
    assert result['outputs']['property_assignments']==[]
    assert result['outputs']['registered_event'] is None
    assert result['outputs']['unknown_case_outputs'] is False


def test_publication_preserves_its_supplied_snapshot(client):
    data=payload()
    data.update(facet='publication',event_index=3,uid=core.TAILS[3][4],dps=[True]*29)
    result=post(client,data).get_json()['result']
    assert result['outputs']['data']==[True]*29
    assert result['outputs']['publication_executed'] is False


@pytest.mark.parametrize('change',[dict(uid='43'),dict(event_index=3),dict(dps=[0]*29)])
def test_invalid_uid_event_or_scalar_refuses(client,change):
    data=payload()
    data.update(change)
    assert post(client,data).status_code==400
