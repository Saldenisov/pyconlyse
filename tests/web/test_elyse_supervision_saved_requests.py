"""Saved request-facet web replay keeps two snapshots and never publishes."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent import saved_requests
from DeviceServers.control.elyse_acq import supervision_requests

client = helpers.client


def payload():
    return dict(facet='supervision_dps',source_id='APP-17',uid='38707',page='ht',gate_dps=[False]*29,
         base_dps=[True]*29,adjustments=[False]*8,commands=[False]*5)


def request(client, data):
    return client.post('/api/elyse/supervision/replay',json=dict(operation='saved_requests',inputs=data))


def test_facade_and_web_use_same_shared_core(client):
    assert supervision_requests.replay_saved_requests is saved_requests.replay_saved_requests
    response=request(client, payload())
    assert response.status_code==200
    result=response.get_json()['result']
    assert result['outputs']['projected_dps']==[i not in (15,17,16,18,19) for i in range(29)]
    assert result['atomic_snapshots_qualified'] is False and result['external_calls_executed'] is False


def test_busy_skips_only_writer_facet(client):
    data=payload()
    data['gate_dps'][28]=True
    data['base_dps']=None
    result=request(client, data).get_json()['result']
    assert result['outputs']['projected_dps'] is None
    assert result['outputs']['other_branches_replayed'] is False


@pytest.mark.parametrize('change',[dict(uid='43'),dict(base_dps=None),dict(commands=[1]*5)])
def test_invalid_site_or_scalar_domain_refuses(client, change):
    data=payload()
    data.update(change)
    assert request(client, data).status_code==400


def test_acquisition_false_entry_does_not_enter_sequence(client):
    result=request(client, dict(facet='acquisition_entry',source_id='APP-00',uid='43',event_index=25,new_value=False)).get_json()['result']
    assert result['outputs']['enters_sequence'] is False
    assert result['outputs']['duration_argument'] is None
    assert result['outputs']['registration_flags']==-2147483647
