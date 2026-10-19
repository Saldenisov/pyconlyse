"""Explicit stop trace facets stay isolated from live equipment."""
import pytest
from tests.web import test_elyse_supervision_saved_xnode as helpers
from legacy.xp_acq_agent.elyse_agent import saved_stop as core

client=helpers.client


def payload(facet='runtime_trace'):
    if facet=='reset':return dict(source_id='APP-00',facet=facet,stage='post_init',
        before=dict(stop=True,tcp_ed=True,emergency_stop=True,general_stop=True))
    return dict(source_id='APP-00',facet=facet,stop_before=True,tcp_before=False,
        schedule=[dict(kind='read_stop',loop_uid=u) for u in reversed(core.RUNTIME_LOOPS)])


@pytest.mark.parametrize('facet',['runtime_trace','reset'])
def test_shared_stop_facet_is_inert(client,facet):
    response=client.post('/api/elyse/supervision/replay',json=dict(operation='saved_stop',inputs=payload(facet)))
    assert response.status_code==200
    result=response.get_json()['result'];assert result['external_calls_executed'] is False
    assert result['physical_stop_qualified'] is False


@pytest.mark.parametrize('change',[dict(source_id='APP-17'),dict(facet='live'),dict(schedule=[dict(kind='outer_tcp_read')])])
def test_unsupported_source_or_join_refuses(client,change):
    data=payload();data.update(change)
    assert client.post('/api/elyse/supervision/replay',json=dict(operation='saved_stop',inputs=data)).status_code==400
