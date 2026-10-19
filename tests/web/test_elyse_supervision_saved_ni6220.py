"""pyconlyse replay uses the actual portable NI6220 projection core."""
from tests.web import test_elyse_supervision_saved_xnode as replay_helpers
import pytest

client = replay_helpers.client


def post(client, count=10, status=True):
    return client.post('/api/elyse/supervision/replay', json=dict(operation='saved_ni6220',
        inputs=dict(source_id='APP-08', uid='612', sample_count=count,
                    returned_channels=[[float(i), float(i + 2)] for i in range(16)],
                    read_error=dict(status=status, code=-17, source='supplied read error'))))


def test_shared_function_identity():
    from DeviceServers.control.elyse_acq import ni6220_projection as modern
    from legacy.xp_acq_agent.elyse_agent import saved_ni6220 as portable
    assert modern.project_ni6220_channel_means is portable.project_ni6220_channel_means
    assert modern.project_saved_ni6220_read is portable.project_saved_ni6220_read
    assert modern.replay_saved_ni6220_read is portable.replay_saved_ni6220_read


@pytest.mark.parametrize('count,length', [(0, 0), (1, 1), (10, 10), (20, 16)])
def test_saved_n_controls_returned_channel_means(client, count, length):
    response = post(client, count)
    assert response.status_code == 200
    assert len(response.json['result']['outputs']['values']) == length
    assert response.json['result']['outputs']['read_error']['status'] is True
    assert response.json['result']['acquired_data_bound'] is False
    assert response.json['execution_allowed'] is False


@pytest.mark.parametrize('count', [-1, True, 2 ** 31])
def test_outside_stored_n_domain_returns400(client, count):
    assert post(client, count).status_code == 400
