"""TOPAS protocol, queue and fault behavior without hardware or network access."""
from copy import deepcopy
import importlib
import json
from threading import Event
from types import SimpleNamespace

import pytest
import requests

from DeviceServers.lasers.topas.client import OutcomeUnknown, TopasClient, TopasError
from DeviceServers.lasers.topas.monitor import TopasMonitor


@pytest.fixture
def rig():
    values = {
        '/Optical/WavelengthControl/Output': {'Wavelength': 600., 'Interaction': 'SH-SIG', 'IsWavelengthStrict': True,
            'IsWavelengthSettingInProgress': False, 'IsWaitingForUserAction': False, 'Messages': []},
        '/ShutterInterlock/State': {'IsShutterOpen': False, 'IsInterlockOpen': False},
        '/Authentication/AuthenticationStatus': {'CallerHasAccess': True, 'AuthenticationHardwareFailure': False},
        '/Optical/WavelengthControl/ExpandedInteractions': [{'Type': 'SH-SIG', 'OutputRange': {'From': 570, 'To': 810}}],
        '/Motors/AllProperties': {'Motors': [{'Index': 1, 'Title': 'Crystal 1'}]},
        '/Optical/WavelengthControl/SetWavelength': {'IsSuccess': True},
        '/ShutterInterlock/IsShutterOpen': False,
    }
    calls = []

    class Session:
        closed = False
        accept_shutter = True

        def request(self, method, url, **options):
            path = url.split('/v0/PublicAPI')[1]
            calls.append((method, path, options))
            value = values.get(path)
            if isinstance(value, Exception):
                raise value
            if self.accept_shutter and method == 'PUT' and path == '/ShutterInterlock/OpenCloseShutter':
                values['/ShutterInterlock/IsShutterOpen'] = options['json']
                values['/ShutterInterlock/State']['IsShutterOpen'] = options['json']
            return SimpleNamespace(status_code=200, content=b'' if value is None else b'json', text='',
                                   json=lambda: deepcopy(value))

        def close(self):
            self.closed = True

    session = Session()
    client = TopasClient('127.0.0.1', 8004, 'T21082', session=session)
    return client, session, values, calls


def writes(calls):
    return [(m, p, o.get('json')) for m, p, o in calls if m != 'GET']


def test_construct_refresh_and_close_have_no_hardware_writes(rig):
    client, session, _, calls = rig
    assert calls == []
    snapshot = client.read_snapshot()
    assert snapshot['serial_number'] == 'T21082' and snapshot['output']['Wavelength'] == 600
    assert len(snapshot['motors']) == 1 and writes(calls) == []
    assert all(v['timeout'] == (2, 2) and v['allow_redirects'] is False for _, _, v in calls)
    assert session.trust_env is False
    client.close()
    assert session.closed and writes(calls) == []


@pytest.mark.parametrize('host,port,serial', [
    ('http://other', 8004, 'T21082'), ('127.0.0.1/path', 8004, 'T21082'),
    ('localhost', 0, 'T21082'), ('localhost', 8004.5, 'T21082'),
    ('localhost', 8004, ''), ('localhost', 8004, '../T21082'),
])
def test_invalid_endpoints_are_rejected(host, port, serial):
    with pytest.raises(ValueError):
        TopasClient(host, port, serial)


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), -1, 0, 100, 900, 'bad'])
def test_invalid_or_uncalibrated_wavelength_never_writes(rig, value):
    client, _, _, calls = rig
    with pytest.raises(ValueError):
        client.set_wavelength(value)
    assert writes(calls) == []


def test_tuning_uses_documented_options_and_reports_vendor_rejection(rig):
    client, _, values, calls = rig
    assert client.set_wavelength(601, 'SH-SIG') == {'IsSuccess': True}
    assert writes(calls) == [('PUT', '/Optical/WavelengthControl/SetWavelength', {
        'Wavelength': 601., 'Interaction': 'SH-SIG', 'IgnoreSeparation': False,
        'DontTouchShutterOnInteractionChange': False, 'SetForBackground': False})]
    values['/Optical/WavelengthControl/SetWavelength'] = {'IsSuccess': False, 'ErrorMessage': 'No calibration'}
    with pytest.raises(TopasError, match='No calibration'):
        client.set_wavelength(601)


@pytest.mark.parametrize('section,key', [
    ('/Authentication/AuthenticationStatus', 'CallerHasAccess'),
    ('/Optical/WavelengthControl/Output', 'IsWavelengthSettingInProgress'),
    ('/Optical/WavelengthControl/Output', 'IsWaitingForUserAction'),
])
def test_unauthorized_or_busy_tuning_never_writes(rig, section, key):
    client, _, values, calls = rig
    values[section][key] = key != 'CallerHasAccess'
    with pytest.raises(TopasError):
        client.set_wavelength(601)
    assert writes(calls) == []


def test_shutter_interlock_is_enforced_and_200_is_not_readback_confirmation(rig):
    client, session, values, calls = rig
    values['/ShutterInterlock/State']['IsInterlockOpen'] = True
    with pytest.raises(TopasError, match='interlock'):
        client.set_shutter(True)
    assert writes(calls) == []
    assert client.set_shutter(False) is False
    values['/ShutterInterlock/State']['IsInterlockOpen'] = False
    assert client.set_shutter(True) is True
    session.accept_shutter = False
    with pytest.raises(TopasError, match='readback'):
        client.set_shutter(False)


def test_manual_confirmation_does_not_restore_open_shutter(rig):
    client, _, values, calls = rig
    with pytest.raises(TopasError, match='No TOPAS operator actions'):
        client.confirm_user_actions()
    assert writes(calls) == []
    values['/Optical/WavelengthControl/Output']['IsWaitingForUserAction'] = True
    client.confirm_user_actions()
    assert writes(calls) == [('PUT', '/Optical/WavelengthControl/FinishWavelengthSettingAfterUserActions', {'RestoreShutter': False})]


def test_timeout_is_not_replayed_and_remains_latched_after_safe_close(rig):
    client, _, values, calls = rig
    values['/Optical/WavelengthControl/SetWavelength'] = requests.Timeout('test timeout')
    monitor = TopasMonitor(client)
    monitor.refresh()
    first = monitor.submit('set_wavelength', 601)
    with pytest.raises(TopasError, match='already pending'):
        monitor.submit('set_wavelength', 602)
    monitor.execute_pending()
    monitor.refresh()
    assert monitor.snapshot()['outcome_unknown']
    assert monitor.snapshot()['operation']['status'] == 'failed'
    with pytest.raises(TopasError, match='outcome is unknown'):
        monitor.submit('set_wavelength', 601)
    monitor.submit('set_shutter', False)
    monitor.execute_pending()
    assert monitor.snapshot()['uncertain_operation']['id'] == first
    assert monitor.snapshot()['outcome_unknown']
    assert sum(p.endswith('/SetWavelength') for _, p, _ in writes(calls)) == 1
    monitor.clear_error()
    assert not monitor.snapshot()['outcome_unknown']


def test_bad_flags_fail_closed_and_failed_reads_retain_visible_stale_snapshot(rig):
    client, _, values, calls = rig
    monitor = TopasMonitor(client)
    monitor.refresh()
    assert monitor.snapshot()['fresh']
    values['/ShutterInterlock/State']['IsShutterOpen'] = 'false'
    monitor.refresh()
    snapshot = monitor.snapshot()
    assert not snapshot['fresh'] and snapshot['data']['output']['Wavelength'] == 600
    with pytest.raises(TopasError, match='status flags'):
        monitor.require_fresh()
    assert writes(calls) == []


def test_slow_snapshot_is_not_falsely_fresh_after_last_request_finishes(rig, monkeypatch):
    client, _, _, _ = rig
    clock = [100.]
    monkeypatch.setattr('DeviceServers.lasers.topas.monitor.time.monotonic', lambda: clock[0])
    data = client.read_snapshot()

    def slow_snapshot():
        clock[0] = 110.
        return data

    monkeypatch.setattr(client, 'read_snapshot', slow_snapshot)
    monitor = TopasMonitor(client)
    monitor.refresh()
    assert monitor.snapshot()['age_s'] == 10
    assert not monitor.snapshot()['fresh']


def test_network_worker_never_blocks_cached_reads_and_runs_one_queued_write():
    entered, release, observed = Event(), Event(), Event()

    class Client:
        def read_snapshot(self):
            entered.set()
            assert release.wait(2)
            return {'output': {}}

        def set_shutter(self, value):
            observed.set()
            return value

        def close(self):
            pass

    monitor = TopasMonitor(Client())
    monitor.start()
    try:
        assert entered.wait(1)
        monitor.submit('set_shutter', False)
        assert monitor.snapshot()['operation']['status'] == 'queued'
        assert not monitor.snapshot()['fresh']
        release.set()
        assert observed.wait(1)
    finally:
        release.set()
        monitor.close()


def test_tango_state_and_attributes_do_not_perform_network_requests(rig, monkeypatch):
    module = importlib.import_module('DeviceServers.lasers.topas.DS_TOPAS')
    monkeypatch.setattr(module.Device, 'set_status', lambda self, value: setattr(self, '_status', value), raising=False)
    device = module.DS_TOPAS()
    client, _, _, calls = rig
    device.monitor = TopasMonitor(client)
    device.configuration_error = ''
    device.monitor.refresh()
    count = len(calls)
    assert device.wavelength_nm() == 600
    assert device.shutter_open() is False
    device.always_executed_hook()
    assert device.get_state() == module.DevState.ON
    device.SetWavelength(601)
    device.always_executed_hook()
    assert device.get_state() == module.DevState.MOVING
    assert json.loads(device.operation_json())['status'] == 'queued'
    assert len(calls) == count


@pytest.mark.parametrize('result', [None, {'IsSuccess': False, 'FailedAfterInteractionSelection': True}])
def test_ambiguous_write_results_are_not_treated_as_ordinary_rejection(rig, result):
    client, _, values, _ = rig
    values['/Optical/WavelengthControl/SetWavelength'] = result
    with pytest.raises(OutcomeUnknown):
        client.set_wavelength(601)
