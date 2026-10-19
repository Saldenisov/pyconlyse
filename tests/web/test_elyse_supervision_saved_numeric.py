from web.backend.elyse_supervision_service import REPLAY_OPERATIONS
from legacy.xp_acq_agent.elyse_agent.saved_numeric import replay_payload
from tests.web import test_elyse_supervision_saved_xnode as helpers

client=helpers.client


def test_same_core_parse_and_format():
    data=dict(operation='parse',decimal_separator='.',use_system_decimal_point=True,text='2.5e-3x',offset=0,default=0.0)
    assert REPLAY_OPERATIONS['saved_numeric'](data) == replay_payload(data)
    data=dict(operation='format',decimal_separator=',',use_system_decimal_point=True,number=4.911,width=5,precision=2)
    assert REPLAY_OPERATIONS['saved_numeric'](data) == replay_payload(data)


def test_locale_profile_required():
    import pytest
    with pytest.raises(ValueError):
        REPLAY_OPERATIONS['saved_numeric'](dict(operation='parse',decimal_separator=None,use_system_decimal_point=True,text='1.0',offset=0,default=0.0))


def test_http_replay(client):
    data=dict(operation='parse',decimal_separator='.',use_system_decimal_point=True,text='2.5e-3x',offset=0,default=0.0)
    response=client.post('/api/elyse/supervision/replay',json=dict(operation='saved_numeric',inputs=data))
    assert response.status_code==200
    assert response.get_json()['result']==replay_payload(data)
    data['decimal_separator']=None
    assert client.post('/api/elyse/supervision/replay',json=dict(operation='saved_numeric',inputs=data)).status_code==400
