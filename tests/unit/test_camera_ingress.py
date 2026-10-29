"""Independent same-DS camera path; fixtures/loopback only, no NI or SQL."""
import copy
import datetime as dt
import importlib
import json
import socket
import threading
import time
from types import SimpleNamespace

import pytest

from DeviceServers.control.elyse_acq.camera_ingress import (
    CameraFrameStore, CameraIngress, load_camera_configuration)
from legacy.xp_acq_control.elyse_agent.camera_stream import CameraFrameQueue, CameraFrameSender

KEY = b'camera-ingress-fixture-key-only-000000000000'
OBSERVED = '2026-10-29T08:00:00.000001+00:00'
WALL = dt.datetime.fromisoformat(OBSERVED).timestamp()


def meta(sequence=1, channel=2, **changes):
    return dict(dict(source_session_id='b' * 32, capture_session_id='a' * 32, sequence=sequence,
        observed_utc=OBSERVED, width=2, height=2, channel=channel, source_age_seconds=.01), **changes)


def envelope():
    return dict(stream_id='c' * 32, message_id=1, receiver_id='d' * 32)


def configuration(**changes):
    return dict(dict(listen_host='127.0.0.1', listen_port=0, key=KEY,
        permitted_peers=('127.0.0.1',), source_mode='LABVIEW_BRIDGE', channels=(), max_channels=2,
        transaction_timeout_seconds=.5, max_clients=2), **changes)


@pytest.fixture
def store():
    clock = [0.]
    value = CameraFrameStore('LABVIEW_BRIDGE', clock=lambda: clock[0], wall_clock=lambda: WALL + clock[0])
    return value, clock


def test_two_actual_channels_are_separate_and_metadata_has_no_pixels(store):
    value, clock = store
    value.accept(meta(channel=2), b'abcd', envelope())
    value.accept(meta(channel=3), b'efgh', envelope())
    assert value.frame_snapshot(2)['frame']['data'] != value.frame_snapshot(3)['frame']['data']
    assert value.frame_snapshot()['channel'] == 3
    status = value.metadata_snapshot()
    assert status['channel_ids'] == [2, 3]
    assert all('frame' not in entry and 'data' not in entry for entry in status['channels'].values())
    assert status['images_archived'] is False
    assert status['hardware_commands_sent'] is False
    assert value.frame_snapshot(9)['reason'] == 'CHANNEL_NOT_OBSERVED'
    assert value.frame_snapshot(9)['frame'] is None


def test_source_run_required_not_fabricated_from_transport(store):
    value, clock = store
    missing = meta()
    del missing['source_session_id']
    with pytest.raises(ValueError, match='actual source_session_id'):
        value.accept(missing, b'abcd', envelope())
    assert value.metadata_snapshot()['channel_ids'] == []


@pytest.mark.parametrize('mode', ['LABVIEW_BRIDGE', 'PYTHON_NATIVE'])
def test_independent_projection_retains_the_existing_exact_video_frame_schema(mode):
    from legacy.xp_acq_control.elyse_agent.federation_wire import validate_video_frame
    value = CameraFrameStore(mode, wall_clock=lambda: WALL)
    value.accept(meta(), b'abcd', envelope())
    projected = value.frame_snapshot(2)
    validate_video_frame(projected['frame'])
    assert projected['source_session_id'] == 'b' * 32
    assert projected['sample_elapsed_seconds_known'] is False
    assert 'sample_elapsed_seconds_known' not in projected['frame']
    assert ('source_session_id' in projected['frame']) == (mode == 'LABVIEW_BRIDGE')


def test_duplicate_retry_does_not_freshen_or_change_pixels(store):
    value, clock = store
    value.accept(meta(), b'abcd', envelope())
    clock[0] = 1.
    value.accept(meta(source_age_seconds=0.), b'abcd', envelope())
    assert value.frame_snapshot()['age_seconds'] == pytest.approx(1.01)
    with pytest.raises(ValueError, match='reused'):
        value.accept(meta(), b'efgh', envelope())
    clock[0] = 2.
    assert value.frame_snapshot()['stale']
    assert value.frame_snapshot()['frame'] is None
    assert value.metadata_snapshot()['duplicate_frames'] == 1


def test_capture_regression_and_retired_capture_never_replace_latest(store):
    value, clock = store
    value.accept(meta(sequence=5), b'abcd', envelope())
    with pytest.raises(ValueError, match='Regressed'):
        value.accept(meta(sequence=4), b'abcd', envelope())
    value.accept(meta(sequence=1, capture_session_id='e' * 32), b'efgh', envelope())
    with pytest.raises(ValueError, match='Retired'):
        value.accept(meta(sequence=6), b'ijkl', envelope())
    assert value.frame_snapshot()['capture_session_id'] == 'e' * 32


def test_wall_clock_age_prevents_old_signed_pixels_claiming_freshness(store):
    value, clock = store
    old = meta(observed_utc='2026-10-29T07:59:30.000001+00:00', source_age_seconds=0.)
    value.accept(old, b'abcd', envelope())
    assert value.frame_snapshot()['age_seconds'] == pytest.approx(30.)
    assert value.frame_snapshot()['frame'] is None
    with pytest.raises(ValueError, match='future'):
        value.accept(meta(observed_utc='2026-10-29T08:00:06.000001+00:00'), b'abcd', envelope())


def test_stale_new_capture_does_not_replace_a_fresh_current_image(store):
    value, clock = store
    value.accept(meta(), b'abcd', envelope())
    value.accept(meta(capture_session_id='e' * 32, source_age_seconds=2.1), b'efgh', envelope())
    assert value.frame_snapshot()['capture_session_id'] == 'a' * 32
    assert value.metadata_snapshot()['stale_frames_received'] == 1


def test_channel_capacity_and_allowlist_reject_instead_of_evicting_images(store):
    value, clock = store
    value.accept(meta(channel=2), b'abcd', envelope())
    value.accept(meta(channel=3), b'efgh', envelope())
    with pytest.raises(ValueError, match='allowlist'):
        value.accept(meta(channel=4), b'ijkl', envelope())
    assert value.metadata_snapshot()['channel_ids'] == [2, 3]
    limited = CameraFrameStore('PYTHON_NATIVE', channels=(2,), wall_clock=lambda: WALL)
    with pytest.raises(ValueError, match='allowlist'):
        limited.accept(meta(channel=3), b'abcd', envelope())


def test_configuration_is_explicit_peer_bound_and_disabled_by_default(tmp_path):
    key = tmp_path / 'camera.key'
    key.write_bytes(KEY)
    path = tmp_path / 'camera.json'
    path.write_text(json.dumps(dict(schema_version=1, enabled=False)))
    assert load_camera_configuration(path) is None
    base = dict(schema_version=1, enabled=True, listen_host='10.20.30.202', listen_port=8769,
                permitted_peers=['10.20.30.2'], key_file='camera.key', source_mode='LABVIEW_BRIDGE')
    path.write_text(json.dumps(base))
    actual = load_camera_configuration(path)
    assert actual['key'] == KEY and actual['max_channels'] == 2
    for changes in (dict(listen_host='0.0.0.0'), dict(permitted_peers=['10.20.30.10']),
                    dict(listen_port=True), dict(source_mode='UNKNOWN'),
                    dict(channels=[2, 3, 4]), dict(max_clients=50),
                    dict(transaction_timeout_seconds=0), dict(key_file='')):
        path.write_text(json.dumps(dict(base, **changes)))
        with pytest.raises(ValueError):
            load_camera_configuration(path)


def test_persistent_binary_ingress_receives_all_frames_and_close_interrupts_idle_reader():
    service = CameraIngress(configuration())
    service.start()
    sender = CameraFrameSender(CameraFrameQueue(), service.server.server_address, KEY)
    # Use an actual current UTC label for the production freshness check.
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        for sequence in range(1, 51):
            assert sender.queue.enqueue(meta(sequence=sequence, observed_utc=now), b'abcd')
        for unused in range(50):
            assert sender.send_once()
        assert service.status()['transport_accepted'] == 50
        assert service.status()['received_bytes'] > 50 * 4
        assert service.status()['sent_ack_bytes'] > 0
        assert service.frame_snapshot(2)['frame']['sequence'] == 50
        assert service.frame_snapshot(2)['hardware_acknowledged'] is False
        started = time.monotonic()
        assert service.close(timeout=2)
        assert time.monotonic() - started < 2
        assert not service.status()['listening']
    finally:
        sender.disconnect()
        service.close()


def test_peer_denied_before_packet_decode_and_handler_creation():
    service = CameraIngress(configuration(permitted_peers=('10.20.30.2',)))
    service.start()
    try:
        with socket.create_connection(service.server.server_address, timeout=1) as connection:
            assert connection.recv(1) == b''
        assert service.status()['rejected_peers'] == 1
        assert service.status()['transport_accepted'] == 0
        assert service.status()['active_connections'] == 0
    finally:
        assert service.close()


def test_bad_authenticated_stream_key_retains_sender_head_and_publishes_no_pixels():
    service = CameraIngress(configuration())
    service.start()
    sender = CameraFrameSender(CameraFrameQueue(), service.server.server_address, b'wrong-fixture-key-00000000000000000000000')
    sender.queue.enqueue(meta(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat()), b'abcd')
    try:
        with pytest.raises(EOFError):
            sender.send_once()
        assert sender.queue.status()['pending'] == 1
        assert service.status()['ingress_errors'] == 1
        assert service.status()['transport_accepted'] == 0
        assert service.frame_snapshot()['frame'] is None
    finally:
        sender.disconnect()
        assert service.close()


def test_client_capacity_rejects_new_connection_without_unbounded_handler_threads():
    service = CameraIngress(configuration(max_clients=1))
    service.start()
    first = socket.create_connection(service.server.server_address, timeout=1)
    try:
        deadline = time.monotonic() + 1
        while service.status()['active_connections'] != 1 and time.monotonic() < deadline:
            time.sleep(.005)
        with socket.create_connection(service.server.server_address, timeout=1) as second:
            assert second.recv(1) == b''
        assert service.status()['rejected_busy'] == 1
        assert service.status()['active_connections'] == 1
    finally:
        first.close()
        assert service.close()


def test_tango_passive_getter_and_metadata_do_not_invoke_xp_command_clients(monkeypatch, store):
    import tango.server
    monkeypatch.setattr(tango.server, 'run', lambda *a, **k: None, raising=False)
    module = importlib.import_module('DeviceServers.control.elyse_acq.DS_AcqTelemetry')
    device = module.DS_AcqTelemetry()
    value, clock = store
    value.accept(meta(), b'abcd', envelope())
    device._camera = SimpleNamespace(frame_snapshot=value.frame_snapshot, status=value.metadata_snapshot)
    device._clients = {'supervision': SimpleNamespace(submit=lambda *a: pytest.fail('Hardware command invoked'))}
    assert json.loads(device.ReadCameraFrame('2'))['frame']['sequence'] == 1
    assert json.loads(device.ReadCameraFrame('3'))['frame'] is None
    assert json.loads(device.video_json())['channel'] == 2
    assert json.loads(device.camera_stream_json())['channel_ids'] == [2]
    for invalid in ('-1', '2.0', '4294967296', '٢', ' '):
        with pytest.raises(ValueError):
            device.ReadCameraFrame(invalid)


def test_tango_legacy_fallback_only_exposes_observed_channel(monkeypatch):
    import tango.server
    monkeypatch.setattr(tango.server, 'run', lambda *a, **k: None, raising=False)
    module = importlib.import_module('DeviceServers.control.elyse_acq.DS_AcqTelemetry')
    device = module.DS_AcqTelemetry()
    device._camera, device._federated, device._migration = None, True, False
    device._store = SimpleNamespace(video_snapshot=lambda: dict(owner='supervision', available=True,
        stale=False, channel=2, frame=dict(data='pixels-fixture')))
    assert json.loads(device.ReadCameraFrame('2'))['frame']['data'] == 'pixels-fixture'
    assert json.loads(device.ReadCameraFrame('1'))['frame'] is None
    status = json.loads(device.camera_stream_json())
    assert status['enabled'] is False and status['channel_ids'] == [2]
    assert 'data' not in json.dumps(status)


def test_auxiliary_camera_configuration_failure_preserves_acquisition27_listener(monkeypatch, tmp_path):
    import tango.server
    monkeypatch.setattr(tango.server, 'run', lambda *a, **k: None, raising=False)
    module = importlib.import_module('DeviceServers.control.elyse_acq.DS_AcqTelemetry')
    servers = []
    def listener(*args, **kwargs):
        server = SimpleNamespace(serve_forever=lambda **k: None, shutdown=lambda: None,
                                 server_close=lambda: None)
        servers.append(server)
        return server
    monkeypatch.setattr(module, 'TelemetrySinkServer', listener)
    device = module.DS_AcqTelemetry()
    key = tmp_path / 'read.key'
    key.write_bytes(KEY)
    broken = tmp_path / 'camera.json'
    broken.write_text('{"schema_version":1,"enabled":true,"listen_host":"0.0.0.0"}')
    device.listen_host = '127.0.0.1'
    device.key_file = str(key)
    device.camera_stream_config_file = str(broken)
    device.set_status = lambda value: None
    device.init_device()
    try:
        assert str(device.get_state()) == 'ON'
        assert len(servers) == 1 and device._server is servers[0]
        assert device._store is not None
        assert json.loads(device.camera_stream_json())['reason'] == 'CAMERA_STREAM_START_FAILED'
        assert json.loads(device.video_json())['frame'] is None
        assert json.loads(device.video_json())['transport'] == 'independent_binary_camera_v2'
    finally:
        device.delete_device()
