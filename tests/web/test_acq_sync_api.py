"""Exact structured synchronization intent at web authorization/dispatch boundary."""
import pytest

from tests.web.test_acq_control_api import api, setup_api, request_command, post, writes


def test_sync_approval_and_tango_receive_exact_pair(setup_api, monkeypatch):
    seen = []
    monkeypatch.setattr(api, 'authorize_runtime_operation', lambda operation, *args, **kwargs: seen.append(operation))
    request = request_command(operation='counter_timing.set', value=dict(counter=7, delay_us=1.25, width_us=3.5))
    reply = post(setup_api, request)
    assert reply.status_code == 200
    assert writes(setup_api)[0][2]['value'] == request['value']
    assert seen[0].args['value'] == request['value']
    assert seen[0].args['operation'] == 'counter_timing.set'


@pytest.mark.parametrize('value', [None, {}, dict(counter=8, delay_us=1., width_us=2.),
    dict(counter=True, delay_us=1., width_us=2.), dict(counter=0, delay_us=0., width_us=2.),
    dict(counter=0, delay_us=1., width_us=-1.), dict(counter=0, delay_us=10 ** 400, width_us=2.),
    dict(counter=0, delay_us=1., width_us=2., bank='C11')])
def test_invalid_sync_pair_never_reaches_tango(setup_api, value):
    assert post(setup_api, request_command(operation='counter_timing.set', value=value)).status_code == 400
    assert writes(setup_api) == []
