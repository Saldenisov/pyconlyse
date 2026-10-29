"""Numeric-only SuperVision beam diagnostics; no motor or card imports.

Image analysis and durable PostgreSQL writes use separate workers. A producer
may submit an observed image without waiting for SQL. References are immutable
history rows; a per-camera revision selects the latest saved centre. Automatic
mode prepares correction proposals only: this module has no motion transport.
"""
from __future__ import annotations

import base64
import copy
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import time

import numpy as np

STALE_SECONDS = 2.0
MAX_RAW_BYTES = 524288
SESSION = re.compile(r'^[0-9a-f]{32}$')
CAMERA = re.compile(r'^ni1409:(0|[1-9][0-9]{0,9})$')
ANALYSIS_VERSION = 'u8_background_subtracted_single_frame_v1'


class RevisionConflict(ValueError):
    pass


class ObservationConflict(ValueError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def camera_channel(camera_id):
    if type(camera_id) is not str or not CAMERA.fullmatch(camera_id):
        raise ValueError('camera_id must identify an actual ni1409 unsigned channel')
    channel = int(camera_id.split(':')[1])
    if channel > 4294967295:
        raise ValueError('Unsigned camera channel required')
    return channel


def reference_revision(value):
    if type(value) is not int or not 0 <= value <= 2**53 - 1:
        raise ValueError('Nonnegative integer expected_revision required')
    return value


def decode_frame(camera_id, value):
    """Validate real bytes/identity, independently of the source freshness flag."""
    channel = camera_channel(camera_id)
    if type(value) is not dict or value.get('owner') != 'supervision':
        raise ValueError('SuperVision image envelope required')
    frame = value.get('frame')
    if type(frame) is not dict:
        return None
    if (frame.get('encoding') != 'base64_raw_row_major' or frame.get('pixel_type') != 'U8'
            or frame.get('simulated') is not False or type(frame.get('channel')) is not int or frame.get('channel') != channel):
        raise ValueError('Actual raw U8 camera/channel observation required')
    width, height = frame.get('width'), frame.get('height')
    if (type(width) is not int or type(height) is not int or min(width, height) < 2
            or width * height > MAX_RAW_BYTES):
        raise ValueError('Bounded image geometry required')
    source = frame.get('source_session_id') or value.get('source_session_id') or value.get('session_id')
    capture, sequence = frame.get('capture_session_id'), frame.get('sequence')
    if (type(source) is not str or type(capture) is not str
            or not SESSION.fullmatch(source) or not SESSION.fullmatch(capture)
            or type(sequence) is not int or not 1 <= sequence <= 2**53 - 1):
        raise ValueError('Bounded source/capture/frame identity required')
    observed = frame.get('observed_utc')
    if type(observed) is not str or len(observed) > 64:
        raise ValueError('Source observation time required')
    parsed = datetime.fromisoformat(observed.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timezone-qualified source observation time required')
    age = value.get('age_seconds')
    if not finite(age) or age < 0:
        raise ValueError('Finite image source age required')
    encoded = frame.get('data')
    if type(encoded) is not str or len(encoded) > 4 * ((MAX_RAW_BYTES + 2) // 3):
        raise ValueError('Bounded base64 camera pixels required')
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) != width * height:
        raise ValueError('Image payload does not match geometry')
    source_kind, processing = frame.get('source'), frame.get('processing')
    if (source_kind not in ('labview_supervision_ni1409', 'python_supervision_ni1409')
            or type(processing) is not str or not 0 < len(processing) <= 100):
        raise ValueError('Known camera source and image-processing coordinates required')
    stable = json.dumps([width, height, source_kind, processing, observed], separators=(',', ':')).encode()
    return dict(camera_id=camera_id, channel=channel, width=width, height=height,
                source_kind=source_kind, processing=processing,
                source_session_id=source, capture_session_id=capture, sequence=sequence,
                frame_identity=f'{source}/{capture}/{sequence}/{channel}',
                observed_utc=observed, age_seconds=float(age),
                source_current=value.get('available') is True and value.get('stale') is False,
                fingerprint=hashlib.sha256(stable + raw).hexdigest(), raw=raw)


def analyse_u8(raw, width, height):
    """Single-frame intensity centroid and marginal profiles; no time averaging.

    Median edge background and MAD noise follow the visibility distinction used
    by laser pointing. A uniform/ambient field is not accepted as a laser spot.
    Ellipse fitting and ROI/SOI selection are intentionally not implemented here.
    """
    gray = np.frombuffer(raw, dtype=np.uint8).reshape(height, width).astype(np.float64)
    border = np.concatenate((gray[0], gray[-1], gray[1:-1, 0], gray[1:-1, -1]))
    background = float(np.median(border))
    noise = float(np.median(np.abs(border - background))) * 1.4826
    floor = background + max(3.0, 4.0 * noise)
    weights = np.maximum(gray - floor, 0.0)
    mask = weights > 0
    fraction = float(np.mean(mask))
    total = float(weights.sum())
    peak = float(gray.max())
    valid = bool(total > 0 and np.count_nonzero(mask) >= 3 and fraction < .60)
    reason = '' if valid else ('No separated beam above background/noise' if fraction < .60
                               else 'Broad illumination cannot identify a laser centroid')
    px = weights.sum(axis=0)
    py = weights.sum(axis=1)
    x = float(np.dot(px, np.arange(width)) / total) if valid else None
    y = float(np.dot(py, np.arange(height)) / total) if valid else None
    return dict(x=x, y=y, valid=valid, reason=reason, peak=peak,
                background=background, threshold=floor, total_intensity=total,
                foreground_fraction=fraction, profiles=dict(x=px.tolist(), y=py.tolist()),
                analysis_version=ANALYSIS_VERSION)


def correction_plan(row, calibration=None):
    """Idempotent preview, never a motor command. Matrix maps pixel error to steps."""
    result = dict(execution_allowed=False, state='MANUAL', reason='Manual mode', proposal=None)
    if row['mode'] != 'auto':
        return result
    current, reference = row['current'], row['reference']
    reason = ('A current valid beam is required' if not current['valid'] else
              'A saved centre with matching image geometry is required' if not row['offset'] else '')
    if reason:
        return dict(result, state='BLOCKED', reason=reason)
    if row['offset']['inside']:
        return dict(result, state='IN_TARGET', reason='Centroid is inside the saved target circle')
    if not isinstance(calibration, dict) or calibration.get('commissioned') is not True:
        return dict(result, state='BLOCKED', reason='Picomotor route and pixel-to-step calibration are not commissioned')
    if any(calibration.get(name) != row.get(name) for name in
           ('camera_id', 'width', 'height', 'source_kind', 'processing', 'coordinate_space')):
        return dict(result, state='BLOCKED', reason='Calibration does not match this camera/geometry/processing coordinate space')
    matrix, axes = calibration.get('pixel_to_steps'), calibration.get('axes')
    maximum, gain = calibration.get('max_steps'), calibration.get('gain', .25)
    if (type(matrix) is not list or len(matrix) != 2
            or any(type(line) is not list or len(line) != 2 or any(not finite(v) for v in line) for line in matrix)
            or type(axes) is not list or len(axes) != 2 or any(type(v) is not str or not v or len(v) > 100 for v in axes)
            or type(maximum) is not int or not 1 <= maximum <= 10000
            or not finite(gain) or not 0 < gain <= 1
            or abs(matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]) < 1e-12):
        return dict(result, state='BLOCKED', reason='Invalid or singular picomotor calibration')
    error = [-row['offset']['dx'], -row['offset']['dy']]
    steps = [max(-maximum, min(maximum, int(round(gain * sum(a * b for a, b in zip(line, error))))))
             for line in matrix]
    identity = json.dumps([row['camera_id'], row['frame_identity'], reference['revision'], row['mode_revision'],
                           matrix, axes, gain, maximum], separators=(',', ':'))
    return dict(result, state='PREVIEW_READY', reason='Correction preview only; physical motor execution is not installed',
                proposal=dict(proposal_id=hashlib.sha256(identity.encode()).hexdigest(),
                              frame_identity=row['frame_identity'], reference_revision=reference['revision'],
                              axes=list(axes), steps=steps, execution_allowed=False))


class CorrectionController:
    """Optional actuator protocol, default dry-run. Run outside camera ingress.

    A commissioned adapter exposes move_relative(axis,steps,request_id). No
    concrete device/Tango/serial adapter is imported or created here. A fault
    fences automatic retry; a caller must explicitly reset before new work.
    """
    def __init__(self, actuator=None, *, live_enabled=False):
        self.actuator, self.live_enabled = actuator, live_enabled is True
        self.seen, self.last_source, self.retired_sources = set(), {}, {}
        self.fault = False

    def reset(self):
        self.fault = False

    def tick(self, row, calibration=None):
        plan = correction_plan(row, calibration)
        if self.fault:
            return dict(plan, state='FAULT', reason='Prior correction result is uncertain; explicit reset required', executed=False)
        current = row['current']
        if (not current['valid'] or not finite(current['age_seconds'])
                or not 0 <= current['age_seconds'] < STALE_SECONDS or plan['proposal'] is None):
            return dict(plan, executed=False)
        camera_id, identity = row['camera_id'], plan['proposal']['proposal_id']
        source = row['source_session_id'], row['capture_session_id']
        prior = self.last_source.get(camera_id)
        retired = self.retired_sources.setdefault(camera_id, set())
        if source in retired:
            return dict(plan, state='ALREADY_PROCESSED', reason='Retired camera capture cannot authorize correction', executed=False)
        if identity in self.seen or prior is not None and source == prior[0] and row['sequence'] <= prior[1]:
            return dict(plan, state='ALREADY_PROCESSED', reason='No replayed correction', executed=False)
        if not self.live_enabled or self.actuator is None:
            return dict(plan, state='DRY_RUN', executed=False)
        if getattr(self.actuator, 'commissioned', False) is not True:
            return dict(plan, state='BLOCKED', reason='Actuator adapter is not commissioned', executed=False)
        self.seen.add(identity)
        if prior is not None and source != prior[0]:
            retired.add(prior[0])
        self.last_source[camera_id] = source, row['sequence']
        if len(self.seen) > 4096:
            self.fault = True
            return dict(plan, state='FAULT', reason='Correction replay ledger full', executed=False)
        try:
            for index, (axis, steps) in enumerate(zip(plan['proposal']['axes'], plan['proposal']['steps'])):
                if steps:
                    self.actuator.move_relative(axis, steps, identity + ':' + str(index))
        except Exception:
            self.fault = True
            return dict(plan, state='FAULT', reason='Correction result unknown; no automatic retry', executed=False)
        return dict(plan, state='EXECUTED', execution_allowed=True, executed=True)


class PostgresDiagnosticsStore:
    """Separate scalar-only tables in the existing local PostgreSQL on F:."""
    configured = True
    def __init__(self, config_path):
        from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore
        self.database = PostgresStore(config_path)

    def initialize(self):
        sql = Path(__file__).with_suffix('.sql').read_text(encoding='utf-8')
        with self.database.connect(writer=True) as connection:
            connection.execute(sql)

    def get_state(self, camera_id):
        camera_channel(camera_id)
        with self.database.connect() as connection:
            state = connection.execute('SELECT reference_revision,mode_revision,mode FROM sup_camera_state WHERE camera_id=%s', (camera_id,)).fetchone()
            if state is None:
                return dict(reference=None, mode='manual', mode_revision=0)
            row = connection.execute('SELECT x,y,radius_px,revision,width,height,saved_utc,frame_identity,source_kind,processing '
                                     'FROM sup_camera_references WHERE camera_id=%s AND revision=%s', (camera_id, state[0])).fetchone()
        reference = None if row is None else dict(x=row[0], y=row[1], radius_px=row[2], revision=row[3],
            width=row[4], height=row[5], saved_utc=row[6].isoformat(), frame_identity=row[7],
            source_kind=row[8], processing=row[9], coordinate_space='displayed_raw_u8_pixels')
        return dict(reference=reference, mode=state[2], mode_revision=state[1])

    def save_reference(self, camera_id, expected_revision, reference):
        camera_channel(camera_id)
        reference_revision(expected_revision)
        with self.database.connect(writer=True) as connection:
            connection.execute('INSERT INTO sup_camera_state(camera_id) VALUES (%s) ON CONFLICT DO NOTHING', (camera_id,))
            revision, = connection.execute('SELECT reference_revision FROM sup_camera_state WHERE camera_id=%s FOR UPDATE', (camera_id,)).fetchone()
            if revision != expected_revision:
                raise RevisionConflict('Saved centre changed; reload latest revision')
            revision += 1
            connection.execute('INSERT INTO sup_camera_references '
                '(camera_id,revision,frame_identity,x,y,radius_px,width,height,saved_utc,source_kind,processing) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (camera_id, revision, reference['frame_identity'], reference['x'], reference['y'], reference['radius_px'],
                 reference['width'], reference['height'], reference['saved_utc'], reference['source_kind'], reference['processing']))
            connection.execute('UPDATE sup_camera_state SET reference_revision=%s WHERE camera_id=%s', (revision, camera_id))
        return dict(reference, revision=revision)

    def set_mode(self, camera_id, expected_revision, mode):
        camera_channel(camera_id)
        reference_revision(expected_revision)
        if mode not in ('manual', 'auto'):
            raise ValueError('Mode must be manual or auto')
        with self.database.connect(writer=True) as connection:
            connection.execute('INSERT INTO sup_camera_state(camera_id) VALUES (%s) ON CONFLICT DO NOTHING', (camera_id,))
            revision, = connection.execute('SELECT mode_revision FROM sup_camera_state WHERE camera_id=%s FOR UPDATE', (camera_id,)).fetchone()
            if revision != expected_revision:
                raise RevisionConflict('Camera mode changed; reload latest revision')
            revision += 1
            connection.execute('UPDATE sup_camera_state SET mode=%s,mode_revision=%s WHERE camera_id=%s', (mode, revision, camera_id))
            connection.execute('INSERT INTO sup_camera_modes(camera_id,revision,mode) VALUES (%s,%s,%s)', (camera_id, revision, mode))
        return dict(mode=mode, mode_revision=revision)

    def write_observations(self, records):
        rows = [(r['camera_id'], r['frame_identity'], r['source_session_id'], r['capture_session_id'], r['sequence'],
                 r['channel'], r['width'], r['height'], r['observed_utc'], r['received_utc'], r['quality'],
                 r['x'], r['y'], r['peak'], r['background'], r['total_intensity'], r['analysis_version'],
                 r['source_kind'], r['processing'], r['source_age_seconds']) for r in records]
        with self.database.connect(writer=True) as connection:
            with connection.cursor() as cursor:
                cursor.executemany('INSERT INTO sup_camera_observations '
                    '(camera_id,frame_identity,source_session_id,capture_session_id,source_sequence,channel,width,height,'
                    'observed_utc,received_utc,quality,x,y,peak,background,total_intensity,analysis_version,source_kind,processing,source_age_seconds) '
                    'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING', rows)


class UnavailableDiagnosticsStore:
    """Analysis remains available; this never pretends references are durable."""
    configured = False

    def __init__(self, reason='PostgreSQL diagnostics configuration unavailable'):
        self.reason = reason

    def initialize(self):
        raise RuntimeError(self.reason)

    def get_state(self, camera_id):
        raise RuntimeError(self.reason)

    def save_reference(self, *args):
        raise RuntimeError(self.reason)

    def set_mode(self, *args):
        raise RuntimeError(self.reason)

    def write_observations(self, records):
        raise RuntimeError(self.reason)


class DiagnosticsService:
    def __init__(self, read_video, store, *, camera_ids=(), clock=None, poll_period=.04,
                 archive_capacity=512, calibrations=None):
        if not callable(read_video) or not .01 <= poll_period <= 2 or type(archive_capacity) is not int or archive_capacity < 1:
            raise ValueError('Reader, bounded polling period and archive capacity required')
        self.read_video, self.store = read_video, store
        self.camera_ids = camera_ids
        self.known = set(camera_ids if not callable(camera_ids) else ())
        for name in self.known:
            camera_channel(name)
        self.clock, self.poll_period = clock or time.monotonic, poll_period
        self.calibrations = copy.deepcopy(calibrations or {})
        self.capacity = archive_capacity
        self.lock, self.ingress = threading.RLock(), threading.Lock()
        self.drain_lock = threading.Lock()
        self.latest, self.states, self.retired = {}, {}, {}
        self.recent = {}
        self.pending = deque()
        self.archive = dict(enabled=getattr(store, 'configured', True), state='STARTING', pending=0, written=0, rejected=0,
                            last_error='', image_pixels_stored=False, durable_ingress=False,
                            reference_persistence='postgresql_transaction')
        self.stop, self.wake = threading.Event(), threading.Event()
        self.threads = None

    def register(self, camera_id):
        camera_channel(camera_id)
        with self.lock:
            if len(self.known) >= 16 and camera_id not in self.known:
                raise ValueError('Camera count limit reached')
            self.known.add(camera_id)

    def observe_video(self, camera_id, payload):
        self.register(camera_id)
        decoded = decode_frame(camera_id, payload)
        if decoded is None:
            # No frame means no observation and never freshens retained metrics.
            return self._row(camera_id)
        now = self.clock()
        with self.ingress:
            with self.lock:
                prior = self.latest.get(camera_id)
                epoch = (decoded['source_session_id'], decoded['capture_session_id'])
                retired = self.retired.setdefault(camera_id, set())
                if epoch in retired:
                    raise ObservationConflict('Retired camera capture cannot replace current observation')
                if prior and prior['epoch'] == epoch:
                    if decoded['sequence'] < prior['data']['sequence']:
                        raise ObservationConflict('Regressed camera frame cannot refresh centroid')
                    if decoded['sequence'] == prior['data']['sequence']:
                        if decoded['fingerprint'] != prior['data']['fingerprint']:
                            raise ObservationConflict('Camera identity reused with different pixels')
                        return self._row(camera_id, sample=prior)
                elif prior:
                    if len(retired) >= 64:
                        raise ObservationConflict('Camera capture history bound reached')
                    retired.add(prior['epoch'])
            metrics = analyse_u8(decoded.pop('raw'), decoded['width'], decoded['height'])
            current = decoded['source_current'] and decoded['age_seconds'] < STALE_SECONDS
            quality = 'CURRENT' if current and metrics['valid'] else 'NO_BEAM' if current else 'STALE'
            record = {name: decoded[name] for name in ('camera_id', 'channel', 'width', 'height',
                'source_session_id', 'capture_session_id', 'sequence', 'frame_identity', 'observed_utc', 'source_kind', 'processing')}
            record.update(received_utc=utc(), quality=quality, x=metrics['x'] if current else None,
                y=metrics['y'] if current else None, peak=metrics['peak'], background=metrics['background'],
                total_intensity=metrics['total_intensity'], analysis_version=ANALYSIS_VERSION, enqueued_at=now,
                source_age_seconds=decoded['age_seconds'])
            with self.lock:
                sample = dict(data=decoded, metrics=metrics, at=now, epoch=epoch)
                self.latest[camera_id] = sample
                # Numeric-only immutable click history; no image byte copies.
                recent = self.recent.setdefault(camera_id, deque(maxlen=64))
                recent.append(dict(data=copy.deepcopy(decoded), at=now, epoch=epoch,
                                   metrics={k: v for k, v in metrics.items() if k != 'profiles'}))
                if len(self.pending) < self.capacity:
                    self.pending.append(record)
                else:
                    self.archive = dict(self.archive, rejected=self.archive['rejected'] + 1,
                                        last_error='Centroid archive queue full; numeric observation not persisted')
                self.archive = dict(self.archive, pending=len(self.pending))
            self.wake.set()
            return self._row(camera_id, sample=sample)

    observe = observe_video

    def _row(self, camera_id, sample=None):
        with self.lock:
            sample = copy.deepcopy(sample if sample is not None else self.latest.get(camera_id))
            state = copy.deepcopy(self.states.get(camera_id, dict(reference=None, mode='manual', mode_revision=0)))
            archive = dict(self.archive)
            archive['oldest_pending_age_seconds'] = (max(0., self.clock() - self.pending[0]['enqueued_at'])
                                                     if self.pending else 0.)
        row = dict(camera_id=camera_id, channel=camera_channel(camera_id), width=None, height=None,
                   source_kind=None, processing=None,
                   source_session_id=None, capture_session_id=None, sequence=None, observed_utc=None,
                   frame_identity=None, current=dict(x=None, y=None, valid=False, age_seconds=None,
                   quality='UNAVAILABLE', reason='No camera observation received'), profiles=dict(x=[], y=[]),
                   reference=state['reference'], mode=state['mode'], mode_revision=state['mode_revision'], offset=None,
                   coordinate_space='displayed_raw_u8_pixels', archive=archive,
                   manual=dict(enabled=False, reason='Picomotor route and calibration are not commissioned'))
        if sample:
            data, metrics = sample['data'], sample['metrics']
            age = data['age_seconds'] + max(0., self.clock() - sample['at'])
            valid = bool(metrics['valid'] and data['source_current'] and age < STALE_SECONDS)
            quality = 'CURRENT' if valid else 'NO_BEAM' if age < STALE_SECONDS and data['source_current'] else 'STALE'
            row.update({name: data[name] for name in ('width', 'height', 'source_session_id', 'capture_session_id',
                                                      'sequence', 'observed_utc', 'frame_identity', 'source_kind', 'processing')})
            row['current'] = dict(x=metrics['x'] if valid else None, y=metrics['y'] if valid else None,
                valid=valid, age_seconds=age, quality=quality,
                reason=metrics['reason'] if quality == 'NO_BEAM' else '' if valid else 'Camera observation expired',
                peak=metrics['peak'], background=metrics['background'], threshold=metrics['threshold'],
                total_intensity=metrics['total_intensity'], analysis_version=ANALYSIS_VERSION)
            row['profiles'] = metrics['profiles']
            reference = row['reference']
            if (valid and reference and (reference['width'], reference['height']) == (data['width'], data['height'])
                    and reference.get('source_kind') == data['source_kind']
                    and reference.get('processing') == data['processing']):
                dx, dy = metrics['x'] - reference['x'], metrics['y'] - reference['y']
                distance = math.hypot(dx, dy)
                row['offset'] = dict(dx=dx, dy=dy, distance_px=distance, inside=distance <= reference['radius_px'])
        row['planner'] = correction_plan(row, self.calibrations.get(camera_id))
        return row

    def snapshot(self, camera_id=None):
        if camera_id is not None:
            self.register(camera_id)
        with self.lock:
            names = [camera_id] if camera_id is not None else sorted(self.known, key=camera_channel)
        return dict(schema_version=1, cameras=[self._row(name) for name in names],
                    execution_allowed=False, hardware_writes=False, observed_utc=utc())

    def refresh(self, camera_id):
        """Optional HTTP/test refresh; the normal worker reads a RAM frame broker."""
        self.observe_video(camera_id, self.read_video(camera_id))

    def load_state(self, camera_id):
        self.register(camera_id)
        value = self.store.get_state(camera_id)
        with self.lock:
            previous = self.states.get(camera_id)
            # A slow reader cannot roll back a completed POST from another thread.
            if previous:
                if (value.get('reference') or {}).get('revision', 0) < (previous.get('reference') or {}).get('revision', 0):
                    value['reference'] = previous['reference']
                if value['mode_revision'] < previous['mode_revision']:
                    value.update(mode=previous['mode'], mode_revision=previous['mode_revision'])
            self.states[camera_id] = copy.deepcopy(value)

    def save_reference(self, payload):
        if type(payload) is not dict or set(payload) != {'camera_id', 'frame_identity', 'expected_revision', 'radius_px'}:
            raise ValueError('Exact reference request required; image pixels/coordinates are not accepted')
        name = payload['camera_id']
        reference_revision(payload['expected_revision'])
        radius = payload['radius_px']
        if not finite(radius) or not .5 <= radius <= 4096:
            raise ValueError('Finite target radius in pixels required')
        self.register(name)
        if type(payload['frame_identity']) is not str or len(payload['frame_identity']) > 150:
            raise ValueError('Bounded observed frame identity required')
        with self.lock:
            sample = next((copy.deepcopy(item) for item in reversed(self.recent.get(name, ()))
                           if item['data']['frame_identity'] == payload['frame_identity']), None)
            latest = self.latest.get(name)
            current_epoch = latest['epoch'] if latest else None
        if (sample is None or sample['epoch'] != current_epoch or not sample['metrics']['valid']
                or not sample['data']['source_current']
                or sample['data']['age_seconds'] + max(0., self.clock() - sample['at']) >= STALE_SECONDS):
            raise ObservationConflict('Selected camera observation expired or its source changed; acquire a valid beam and retry')
        data, measured = sample['data'], sample['metrics']
        if radius > math.hypot(data['width'], data['height']):
            raise ValueError('Target radius exceeds image geometry')
        reference = dict(x=measured['x'], y=measured['y'], radius_px=float(radius),
                         width=data['width'], height=data['height'], saved_utc=utc(), frame_identity=data['frame_identity'],
                         source_kind=data['source_kind'], processing=data['processing'], coordinate_space='displayed_raw_u8_pixels')
        self.store.save_reference(name, payload['expected_revision'], reference)
        self.load_state(name)
        return self.snapshot(name)

    def set_mode(self, payload):
        if type(payload) is not dict or set(payload) != {'camera_id', 'mode', 'expected_revision'}:
            raise ValueError('Exact mode request required')
        if payload['mode'] not in ('manual', 'auto'):
            raise ValueError('Mode must be manual or auto')
        name = payload['camera_id']
        self.register(name)
        self.store.set_mode(name, reference_revision(payload['expected_revision']), payload['mode'])
        self.load_state(name)
        return self.snapshot(name)

    def drain_once(self):
        with self.drain_lock:
            return self._drain_once()

    def _drain_once(self):
        with self.lock:
            records = list(self.pending)[:32]
        if not records:
            return 0
        self.store.write_observations(records)
        with self.lock:
            for record in records:
                if self.pending[0]['frame_identity'] != record['frame_identity'] or self.pending[0]['camera_id'] != record['camera_id']:
                    raise RuntimeError('Centroid archive FIFO identity changed')
                self.pending.popleft()
            self.archive = dict(self.archive, state='RUNNING', written=self.archive['written'] + len(records),
                                pending=len(self.pending), last_error='')
        return len(records)

    def _poll(self):
        while not self.stop.is_set():
            if callable(self.camera_ids):
                try:
                    for name in self.camera_ids():
                        self.register(name)
                except Exception:
                    pass
            with self.lock:
                names = list(self.known)
            for name in names:
                if self.stop.is_set():
                    break
                try:
                    self.refresh(name)
                except Exception:
                    # Previous source age keeps increasing; no false current refresh.
                    pass
            self.stop.wait(self.poll_period)

    def _write(self):
        initialized, loaded, refresh_at = False, set(), 0.
        while not self.stop.is_set():
            try:
                if not initialized:
                    self.store.initialize()
                    initialized = True
                with self.lock:
                    known = set(self.known)
                if self.clock() >= refresh_at or known - loaded:
                    for name in known:
                        self.load_state(name)
                    loaded, refresh_at = known, self.clock() + 1.
                if self.drain_once():
                    continue
                with self.lock:
                    self.archive = dict(self.archive, state='RUNNING', last_error='')
                self.wake.wait(.2)
                self.wake.clear()
            except Exception as error:
                with self.lock:
                    self.archive = dict(self.archive, state='DEGRADED', last_error=type(error).__name__)
                self.stop.wait(1.)

    def start(self, *, poll=True):
        if self.threads is not None:
            raise RuntimeError('Diagnostics already started')
        self.threads = [threading.Thread(target=self._write, name='supervision-centroid-postgres', daemon=True)]
        if poll:
            self.threads.append(threading.Thread(target=self._poll, name='supervision-centroid-analysis', daemon=True))
        for thread in self.threads:
            thread.start()

    def close(self, timeout=5):
        self.stop.set()
        self.wake.set()
        deadline = time.monotonic() + timeout
        for thread in self.threads or ():
            thread.join(max(0., deadline - time.monotonic()))
        return all(not thread.is_alive() for thread in self.threads or ())
