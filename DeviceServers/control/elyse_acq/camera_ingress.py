"""Optional binary camera ingress owned by the existing Everest Tango DS.

No card, command client or archive dependency. Each actual channel has one
bounded RAM image; the authenticated stream is independent of Acquisition's
27-bank telemetry ingress and database. Import starts no listener or worker.
"""
from __future__ import annotations

import base64
from collections import deque
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import socket
import socketserver
import threading
import time

from legacy.xp_acq_control.elyse_agent.camera_stream import CameraFrameReceiver, validate_frame
from legacy.xp_acq_control.elyse_agent.telemetry_relay import DeadlineSocket, canonical
from legacy.xp_acq_control.elyse_agent.supervision_wire import validate_key

TRANSPORT = 'independent_binary_camera_v2'
PROCESSING = 'raw_grab_before_legacy_interlace_bcg_profiles'
SOURCES = {'LABVIEW_BRIDGE': 'labview_supervision_ni1409',
           'PYTHON_NATIVE': 'python_supervision_ni1409'}


def load_camera_configuration(path):
    """Explicit local deployment file only; never configured by an HTTP request."""
    config_path = Path(path)
    value = json.loads(config_path.read_text(encoding='utf-8'))
    names = {'schema_version', 'enabled', 'listen_host', 'listen_port', 'key_file',
             'permitted_peers', 'source_mode', 'channels', 'max_channels',
             'transaction_timeout_seconds', 'max_clients'}
    if (type(value) is not dict or set(value) - names or type(value.get('schema_version')) is not int
            or value.get('schema_version') != 1
            or type(value.get('enabled')) is not bool):
        raise ValueError('Exact camera stream configuration required')
    if not value['enabled']:
        return None
    host, port = value.get('listen_host'), value.get('listen_port')
    if host not in ('127.0.0.1', '10.20.30.202') or type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Explicit Everest camera listener required')
    peers = value.get('permitted_peers')
    allowed_peers = ('127.0.0.1',) if host == '127.0.0.1' else ('10.20.30.2',)
    if (type(peers) is not list or not peers or len(peers) > 2
            or any(type(peer) is not str or peer not in allowed_peers for peer in peers)
            or len(set(peers)) != len(peers)):
        raise ValueError('Camera listener must be bound to its explicit SuperVision peer')
    mode = value.get('source_mode')
    if mode not in SOURCES:
        raise ValueError('Explicit native or LabVIEW camera source mode required')
    channels, max_channels = value.get('channels', []), value.get('max_channels', 2)
    if (type(channels) is not list or any(type(c) is not int or not 0 <= c <= 0xFFFFFFFF for c in channels)
            or len(set(channels)) != len(channels) or type(max_channels) is not int
            or not 1 <= max_channels <= 4 or len(channels) > max_channels):
        raise ValueError('Bounded actual channel allowlist required')
    timeout, max_clients = value.get('transaction_timeout_seconds', 2.), value.get('max_clients', 2)
    if (type(timeout) not in (int, float) or not math.isfinite(timeout) or not .1 <= timeout <= 5
            or type(max_clients) is not int or not 1 <= max_clients <= 4):
        raise ValueError('Bounded camera connection limits required')
    key_name = value.get('key_file')
    if type(key_name) is not str or not key_name:
        raise ValueError('Camera authentication key file required')
    key_path = Path(key_name)
    if not key_path.is_absolute():
        key_path = config_path.parent / key_path
    return dict(listen_host=host, listen_port=port, key=validate_key(key_path.read_bytes().strip()),
                permitted_peers=tuple(peers), source_mode=mode, channels=tuple(channels),
                max_channels=max_channels, transaction_timeout_seconds=float(timeout), max_clients=max_clients)


class CameraFrameStore:
    """Immutable byte snapshots, per-channel source ages and retired-capture guards."""
    def __init__(self, source_mode, *, channels=(), max_channels=2, clock=None, wall_clock=None):
        if source_mode not in SOURCES or type(max_channels) is not int or not 1 <= max_channels <= 4:
            raise ValueError('Known source mode and bounded channel count required')
        self.source_mode, self.channels, self.max_channels = source_mode, tuple(channels), max_channels
        self.clock, self.wall_clock = clock or time.monotonic, wall_clock or time.time
        self.lock = threading.Lock()
        self.latest, self.retired, self.samples = {}, {}, {}
        self.source_gaps = {}
        self.latest_channel = None
        self.accepted = self.duplicates = self.stale_received = self.channel_rejected = 0
        self.closed = False

    def accept(self, metadata, pixels, envelope):
        validate_frame(metadata, pixels)
        # A transport session is not evidence of a native VI/card run identity.
        if 'source_session_id' not in metadata:
            raise ValueError('Camera ingress requires the actual source_session_id')
        source, capture, channel = metadata['source_session_id'], metadata['capture_session_id'], metadata['channel']
        observed_time = dt.datetime.fromisoformat(metadata['observed_utc'].replace('Z', '+00:00'))
        observed = observed_time.timestamp()
        now, wall = self.clock(), self.wall_clock()
        if observed > wall + 5:
            raise ValueError('Camera observation clock is more than 5 seconds in the future')
        age = max(metadata['source_age_seconds'], max(0., wall - observed))
        immutable = dict(metadata)
        immutable.pop('source_age_seconds')
        digest = hashlib.sha256(canonical(immutable) + pixels).hexdigest()
        # Encoding does not hold the RAM-view lock or any telemetry/SQL lock.
        encoded = base64.b64encode(pixels).decode('ascii')
        frame = dict(metadata, observed_utc=observed_time.isoformat(), source=SOURCES[self.source_mode], simulated=False,
            sequence_interpretation='software grab observation, not hardware frame counter',
            sample_elapsed_seconds=0.,
            pixel_type='U8', encoding='base64_raw_row_major', data=encoded,
            processing=PROCESSING, hardware_acknowledged=False)
        if self.source_mode == 'PYTHON_NATIVE':
            # Keep the exact existing native-video schema. Source-run identity
            # remains explicit in the outer projection and cache identity.
            frame.pop('source_session_id')
        with self.lock:
            if self.closed:
                raise RuntimeError('Camera store is closed')
            if ((self.channels and channel not in self.channels)
                    or channel not in self.latest and len(self.latest) >= self.max_channels):
                self.channel_rejected += 1
                raise ValueError('Camera channel is not admitted by the bounded channel allowlist')
            prior = self.latest.get(channel)
            identity = source, capture
            retired = self.retired.setdefault(channel, set())
            if identity in retired:
                raise ValueError('Retired camera capture cannot become current again')
            if prior:
                same = identity == prior['identity']
                if same and metadata['sequence'] < prior['frame']['sequence']:
                    raise ValueError('Regressed camera observation sequence')
                if same and metadata['sequence'] == prior['frame']['sequence']:
                    if digest != prior['digest']:
                        raise ValueError('Camera observation identity reused with different pixels or geometry')
                    self.duplicates += 1
                    return
                if not same and observed < prior['observed']:
                    raise ValueError('Older capture cannot replace a newer camera observation')
                if not same and len(retired) >= 64:
                    raise ValueError('Camera capture-session history bound reached')
                prior_age = prior['age'] + max(0., now - prior['at'])
                if age >= 2 and prior_age < 2:
                    self.stale_received += 1
                    self.accepted += 1
                    return
                if not same:
                    retired.add(prior['identity'])
                else:
                    self.source_gaps[channel] = self.source_gaps.get(channel, 0) + max(
                        0, metadata['sequence'] - prior['frame']['sequence'] - 1)
            self.latest[channel] = dict(frame=frame, identity=identity, at=now, age=age,
                digest=digest, observed=observed, envelope=copy.deepcopy(envelope))
            arrivals = self.samples.setdefault(channel, deque(maxlen=256))
            arrivals.append(now)
            self.latest_channel = channel
            self.accepted += 1
            self.stale_received += age >= 2

    def _view(self, channel, now, pixels):
        row = self.latest.get(channel)
        common = dict(schema_version=1, owner='supervision', transport=TRANSPORT,
            storage_mode='ram_latest_per_channel', images_archived=False,
            read_only=True, hardware_acknowledged=False, physical_measurements_verified=False,
            source_mode=self.source_mode, channel=channel)
        if row is None:
            return dict(common, available=False, stale=True, frame=None,
                        reason='CHANNEL_NOT_OBSERVED' if channel is not None else 'CAMERA_STREAM_WAITING')
        age = row['age'] + max(0., now - row['at'])
        available = not self.closed and age < 2
        frame = row['frame']
        value = dict(common, **{name: frame[name] for name in (
            'source', 'capture_session_id', 'sequence', 'width', 'height',
            'pixel_type', 'encoding', 'processing', 'observed_utc')},
            source_session_id=row['identity'][0], session_id=row['identity'][0],
            sample_elapsed_seconds_known=False, age_seconds=age, available=available, stale=not available,
            frame_identity='{}:{}:{}:{}'.format(row['identity'][0], frame['capture_session_id'],
                                               channel, frame['sequence']),
            transport_session_id=row['envelope']['stream_id'],
            transport_message_id=row['envelope']['message_id'],
            source_sequence_gaps=self.source_gaps.get(channel, 0),
            source_sequence_gap_interpretation='Includes upstream skips or intentional decimation; not a hardware loss counter')
        arrivals = [at for at in self.samples[channel] if now - at <= 2]
        value['observed_hz'] = ((len(arrivals) - 1) / (arrivals[-1] - arrivals[0])
                                if len(arrivals) > 1 and arrivals[-1] > arrivals[0] else 0.)
        if pixels:
            value['frame'] = copy.deepcopy(frame) if available else None
            if value['frame'] is not None:
                value['frame']['source_age_seconds'] = age
        return value

    def frame_snapshot(self, channel=None):
        if channel is not None and (type(channel) is not int or not 0 <= channel <= 0xFFFFFFFF):
            raise ValueError('Actual unsigned camera channel required')
        with self.lock:
            return self._view(self.latest_channel if channel is None else channel, self.clock(), True)

    def metadata_snapshot(self):
        with self.lock:
            now = self.clock()
            return dict(schema_version=1, enabled=True, transport=TRANSPORT, owner='supervision',
                channel_ids=sorted(self.latest), selected_channel=self.latest_channel,
                channels={str(channel): self._view(channel, now, False) for channel in sorted(self.latest)},
                accepted_frames=self.accepted, duplicate_frames=self.duplicates,
                stale_frames_received=self.stale_received, channel_rejected=self.channel_rejected,
                max_channels=self.max_channels, stale_after_seconds=2,
                images_archived=False, hardware_commands_sent=False)

    def close(self):
        with self.lock:
            self.closed = True


class _CameraHandler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        meter = _MeteredSocket(self.request)
        last_received = last_sent = 0
        try:
            self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            while not server.closing.is_set():
                server.receiver.receive_once(DeadlineSocket(
                    meter, time.monotonic() + server.transaction_timeout))
                server.record_traffic(meter.received - last_received, meter.sent - last_sent)
                last_received, last_sent = meter.received, meter.sent
        except EOFError:
            pass
        except Exception as error:
            if not server.closing.is_set():
                with server.active_changed:
                    server.failures += 1
                    server.last_error = type(error).__name__ + ': ' + str(error)[:180]
        finally:
            server.record_traffic(meter.received - last_received, meter.sent - last_sent)
            with server.active_changed:
                server.active.discard(self.request)
                server.active_changed.notify_all()


class _MeteredSocket:
    def __init__(self, connection):
        self.connection, self.received, self.sent = connection, 0, 0

    def settimeout(self, timeout):
        self.connection.settimeout(timeout)

    def recv(self, count):
        value = self.connection.recv(count)
        self.received += len(value)
        return value

    def sendall(self, value):
        self.connection.sendall(value)
        self.sent += len(value)


class CameraIngressServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address, store, key, permitted_peers, *, transaction_timeout=2., max_clients=2):
        self.store = store
        self.receiver = CameraFrameReceiver(key, store.accept, with_envelope=True)
        self.permitted_peers = tuple(permitted_peers)
        self.transaction_timeout = transaction_timeout
        self.slots = threading.BoundedSemaphore(max_clients)
        self.active_changed = threading.Condition()
        self.active = set()
        self.closing = threading.Event()
        self.failures = self.peer_rejected = self.busy_rejected = 0
        self.received_bytes = self.sent_bytes = 0
        self.started_at = time.monotonic()
        self.traffic = deque(maxlen=256)
        self.last_error = ''
        super().__init__(address, _CameraHandler)

    def process_request(self, request, client_address):
        if self.closing.is_set() or client_address[0] not in self.permitted_peers:
            self.peer_rejected += 1
            self.shutdown_request(request)
            return
        if not self.slots.acquire(blocking=False):
            self.busy_rejected += 1
            self.shutdown_request(request)
            return
        with self.active_changed:
            self.active.add(request)
        try:
            super().process_request(request, client_address)
        except Exception:
            with self.active_changed:
                self.active.discard(request)
                self.active_changed.notify_all()
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def status(self):
        value = self.store.metadata_snapshot()
        with self.active_changed:
            now = time.monotonic()
            recent = sum(size for at, size in self.traffic if now - at <= 2)
            window = max(.001, min(2., now - self.started_at))
            value.update(active_connections=len(self.active), rejected_peers=self.peer_rejected,
                rejected_busy=self.busy_rejected, ingress_errors=self.failures, last_error=self.last_error,
                transport_accepted=self.receiver.accepted, transport_duplicates=self.receiver.duplicates,
                receiver_session_id=self.receiver.receiver_id,
                unknown_ack_prefix_streams=self.receiver.unknown_prefix_streams,
                received_bytes=self.received_bytes, sent_ack_bytes=self.sent_bytes,
                ingress_mbit_s_window=recent * 8 / window / 1e6, bandwidth_window_seconds=window,
                listening=not self.closing.is_set())
        return value

    def record_traffic(self, received, sent):
        if not received and not sent:
            return
        with self.active_changed:
            self.received_bytes += received
            self.sent_bytes += sent
            self.traffic.append((time.monotonic(), received))


class CameraIngress:
    """Explicitly started DS-owned listener with bounded, retryable shutdown."""
    def __init__(self, configuration):
        self.store = CameraFrameStore(configuration['source_mode'], channels=configuration['channels'],
                                      max_channels=configuration['max_channels'])
        self.server = CameraIngressServer((configuration['listen_host'], configuration['listen_port']),
            self.store, configuration['key'], configuration['permitted_peers'],
            transaction_timeout=configuration['transaction_timeout_seconds'], max_clients=configuration['max_clients'])
        self.thread = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Camera ingress already started')
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .05}, name='camera-stream-listener', daemon=True)
        self.thread.start()

    def frame_snapshot(self, channel=None):
        return self.store.frame_snapshot(channel)

    def status(self):
        return self.server.status()

    def close(self, timeout=3):
        deadline = time.monotonic() + timeout
        self.server.closing.set()
        with self.server.active_changed:
            active = tuple(self.server.active)
        for connection in active:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self.thread is not None and self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(max(0., deadline - time.monotonic()))
        with self.server.active_changed:
            while self.server.active and time.monotonic() < deadline:
                self.server.active_changed.wait(max(0., deadline - time.monotonic()))
            if self.server.active or self.thread is not None and self.thread.is_alive():
                return False
        self.server.server_close()
        self.store.close()
        return True
