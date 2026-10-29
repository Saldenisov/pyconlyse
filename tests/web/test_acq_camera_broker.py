"""Camera web fan-out/stream tests: fixtures only, no Tango/XP/SQL calls."""
import importlib
import json
from pathlib import Path
import sys
import threading
import time
import zlib

import pytest
from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from acq_camera_broker import CameraFrameBroker, gzip_events


def image(sequence=1, age=.1):
    return dict(owner='supervision', available=True, stale=False, age_seconds=age,
                session_id='a' * 32, frame=dict(source_session_id='b' * 32,
                    capture_session_id='c' * 32, sequence=sequence, channel=2),
                diagnostics=dict(current=dict(valid=True, age_seconds=age, quality='CURRENT')))


def inert(clock=None):
    def forbidden(*args):
        raise AssertionError('Source I/O attempted')
    broker = CameraFrameBroker(forbidden, forbidden, clock=clock or time.monotonic)
    broker.start = lambda: None
    return broker


def test_duplicate_observation_cannot_refresh_its_age_or_stale_centroid():
    clock = [0.]
    broker = inert(lambda: clock[0])
    broker.publish(2, image())
    clock[0] = 1.
    broker.publish(2, image(age=0.))
    assert broker.snapshot(2)['age_seconds'] == 1.1
    clock[0] = 2.
    snapshot = broker.snapshot(2)
    assert snapshot['frame'] is None and snapshot['stale']
    assert snapshot['diagnostics']['current']['valid'] is False


def test_events_emit_next_frame_at25hz_without_one_second_gate_or_backlog():
    broker = inert()
    broker.publish(2, image(1))
    events = broker.events(2, fps=25)
    first = next(events)
    for sequence in range(2, 30):
        broker.publish(2, image(sequence))
    second = next(events)
    assert b'"sequence":1,' in first
    assert b'"sequence":29,' in second
    assert len(broker.entries) == 1
    events.close()
    assert broker.subscribers == {}


def test_gzip_flushes_each_event_immediately_without_waiting_for_another_frame():
    events = gzip_events(iter([b'event: frame\ndata: {"sequence":1}\n\n',
                               b'event: frame\ndata: {"sequence":2}\n\n']))
    decoder = zlib.decompressobj(31)
    assert b'"sequence":1' in decoder.decompress(next(events))
    assert b'"sequence":2' in decoder.decompress(next(events))
    events.close()


def test_metadata_contract_is_valid_when_empty_and_old_freshness_expires():
    clock = [0.]
    broker = inert(lambda: clock[0])
    assert broker.channels()['channel_ids'] == []
    assert broker.channels()['owner'] == 'supervision'
    broker.metadata = {'channel_ids': [2], 'channels': {'2': {'available': True, 'stale': False, 'age_seconds': .1}}}
    broker.metadata_at = 0.
    clock[0] = 3.
    assert broker.channels()['channels']['2']['stale'] is True
    assert broker.channels()['channels']['2']['age_seconds'] == 3.1


def test_subscriber_reservation_has_a_bounded_rejection_before_stream_headers():
    broker = inert()
    broker.max_subscribers = 1
    reserved = broker.subscribe(2)
    reserved.__enter__()
    try:
        with pytest.raises(ValueError, match='subscriber capacity'):
            with broker.subscribe(3):
                pass
    finally:
        reserved.__exit__(None, None, None)


def test_source_latency_is_charged_to_camera_age_before_decoration():
    clock = [0.]
    decorated, ready = [], threading.Event()
    broker = None
    def read(channel):
        clock[0] += 1.5
        return image(age=.1)
    broker = CameraFrameBroker(read, lambda: {'channel_ids': [2], 'selected_channel': 2},
                               clock=lambda: clock[0])
    def decorate(name, value):
        decorated.append(value['age_seconds'])
        ready.set()
        broker.stop.set()
        return value['diagnostics']
    broker.decorate = decorate
    try:
        broker.snapshot(2, wait=0)
        assert ready.wait(1)
        assert decorated == [1.6]
    finally:
        assert broker.close()


def test_view_capacity_is_bounded_and_expired_channels_are_reaped():
    clock = [0.]
    broker = inert(lambda: clock[0])
    for channel in range(8):
        broker.snapshot(channel, wait=0)
    with pytest.raises(ValueError, match='capacity'):
        broker.snapshot(9, wait=0)
    clock[0] = 3.
    broker.snapshot(9, wait=0)
    assert len(broker.demand) == 1


def test_one_blocked_source_read_does_not_hold_browser_cache_lock():
    entered, release = threading.Event(), threading.Event()
    def source(channel):
        entered.set()
        release.wait(2)
        return image()
    broker = CameraFrameBroker(source, lambda: {'channel_ids': [2]})
    try:
        broker.snapshot(2, wait=0)
        assert entered.wait(1)
        start = time.monotonic()
        assert broker.snapshot(2, wait=0)['available'] is False
        assert time.monotonic() - start < .1
        assert broker.thread.name == 'supervision-camera-web'
    finally:
        release.set()
        assert broker.close()


def test_sse_query_limits_compression_and_existing_auth_gate(monkeypatch):
    api = importlib.import_module('acq_telemetry_api')
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'false')
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'false')
    app = Flask(__name__)
    from flask_jwt_extended import JWTManager
    app.config['JWT_SECRET_KEY'] = 'fixture-only-secret-00000000000000'
    JWTManager(app)
    app.register_blueprint(api.acq_telemetry_api)
    class Broker:
        def events(self, channel, fps):
            assert channel == 2 and fps == 12.5
            return iter([b'event: status\ndata: {"available":false}\n\n'])
    app.extensions['supervision_camera_broker'] = Broker()
    client = app.test_client()
    root = '/api/elyse/acquisition/telemetry/video/stream'
    assert client.get(root + '?fps=1').status_code == 400
    assert client.get(root + '?channel=-1').status_code == 400
    assert client.get(root + '?channel=2&channel=3').status_code == 400
    response = client.get(root + '?channel=2&fps=12.5', headers={'Accept-Encoding': 'gzip'})
    assert response.status_code == 200 and response.headers['Content-Encoding'] == 'gzip'
    assert b'"available":false' in zlib.decompressobj(31).decompress(response.data)
    response = client.get(root + '?channel=2&fps=12.5', headers={'Accept-Encoding': 'gzip;q=0'})
    assert 'Content-Encoding' not in response.headers
    monkeypatch.setenv('PYCONLYSE_ENFORCE_DEVICE_AUTH', 'true')
    assert client.get(root).status_code == 401
