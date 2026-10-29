"""Centroid/reference state and dry-run controller; fixtures only, no motors."""
import base64
import copy
from pathlib import Path
import sys
import threading
import time

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'web/backend'))
from supervision_diagnostics import (DiagnosticsService, RevisionConflict, ObservationConflict,
    CorrectionController, correction_plan, UnavailableDiagnosticsStore, analyse_u8)

CAMERA = 'ni1409:2'


def video(sequence=1, x=6, y=4, *, channel=2, capture='b' * 32, source='a' * 32,
          width=12, height=10, age=.1, uniform=False, processing='raw_grab_before_legacy_interlace_bcg_profiles'):
    raw = np.full((height, width), 10, dtype=np.uint8)
    if not uniform:
        raw[y - 1:y + 2, x - 1:x + 2] = 210
    return dict(owner='supervision', available=True, stale=False, age_seconds=age, session_id=source,
        frame=dict(source='labview_supervision_ni1409', source_session_id=source, capture_session_id=capture,
            sequence=sequence, channel=channel, width=width, height=height,
            pixel_type='U8', simulated=False, encoding='base64_raw_row_major',
            processing=processing, observed_utc='2026-10-29T08:00:00.000001+00:00',
            data=base64.b64encode(raw.tobytes()).decode('ascii')))


class MemoryStore:
    configured = True

    def __init__(self):
        self.states, self.references, self.modes, self.records = {}, [], [], {}
        self.lock = threading.Lock()
        self.fail = False

    def initialize(self):
        if self.fail:
            raise RuntimeError('fixture offline')

    def get_state(self, camera_id):
        with self.lock:
            return copy.deepcopy(self.states.get(camera_id, dict(reference=None, mode='manual', mode_revision=0)))

    def save_reference(self, camera_id, expected, reference):
        if self.fail:
            raise RuntimeError('fixture offline')
        with self.lock:
            state = self.states.setdefault(camera_id, dict(reference=None, mode='manual', mode_revision=0))
            revision = (state['reference'] or {}).get('revision', 0)
            if revision != expected:
                raise RevisionConflict('fixture centre conflict')
            saved = dict(reference, revision=revision + 1)
            self.references.append(copy.deepcopy(saved))
            state['reference'] = copy.deepcopy(saved)
            return saved

    def set_mode(self, camera_id, expected, mode):
        if self.fail:
            raise RuntimeError('fixture offline')
        with self.lock:
            state = self.states.setdefault(camera_id, dict(reference=None, mode='manual', mode_revision=0))
            if state['mode_revision'] != expected:
                raise RevisionConflict('fixture mode conflict')
            state.update(mode=mode, mode_revision=expected + 1)
            self.modes.append(dict(mode=mode, mode_revision=expected + 1))
            return self.modes[-1]

    def write_observations(self, records):
        if self.fail:
            raise RuntimeError('fixture offline')
        for row in records:
            self.records.setdefault((row['camera_id'], row['frame_identity']), copy.deepcopy(row))


@pytest.fixture
def rig():
    now, store, payload = [0.], MemoryStore(), [video()]
    service = DiagnosticsService(lambda name: copy.deepcopy(payload[0]), store,
                                 camera_ids=(CAMERA,), clock=lambda: now[0])
    service.observe(CAMERA, payload[0])
    return service, store, now, payload


def request_reference(row, expected=0, radius=2.):
    return dict(camera_id=CAMERA, frame_identity=row['frame_identity'], expected_revision=expected, radius_px=radius)


def test_single_frame_raw_centroid_and_profiles(rig):
    service, _, _, _ = rig
    row = service.snapshot(CAMERA)['cameras'][0]
    assert row['current']['x'] == pytest.approx(6)
    assert row['current']['y'] == pytest.approx(4)
    assert row['current']['quality'] == 'CURRENT'
    assert row['coordinate_space'] == 'displayed_raw_u8_pixels'
    assert len(row['profiles']['x']) == 12 and len(row['profiles']['y']) == 10
    assert sum(row['profiles']['x']) == sum(row['profiles']['y'])


def test_uniform_field_and_stale_frames_never_supply_current_centroid(rig):
    service, _, now, _ = rig
    row = service.observe(CAMERA, video(2, uniform=True))
    assert row['current']['quality'] == 'NO_BEAM'
    assert row['current']['x'] is None and row['current']['valid'] is False
    row = service.observe(CAMERA, video(3, age=3.))
    assert row['current']['quality'] == 'STALE' and row['current']['x'] is None
    service.observe(CAMERA, video(4))
    now[0] = 2.
    assert service.snapshot(CAMERA)['cameras'][0]['current']['quality'] == 'STALE'


@pytest.mark.parametrize('mutation', [lambda p: p['frame'].update(simulated=True),
    lambda p: p['frame'].update(data='@@@@'), lambda p: p['frame'].update(channel=True),
    lambda p: p['frame'].update(width=True), lambda p: p['frame'].update(capture_session_id='bad'),
    lambda p: p.update(age_seconds=float('nan'))])
def test_invalid_frames_are_rejected_without_persisting(rig, mutation):
    service, _, _, _ = rig
    payload = video(2)
    mutation(payload)
    with pytest.raises(ValueError):
        service.observe(CAMERA, payload)
    assert service.snapshot(CAMERA)['cameras'][0]['archive']['pending'] == 1


def test_duplicate_does_not_refresh_age_or_enqueue_another_observation(rig):
    service, _, now, _ = rig
    now[0] = 1.
    row = service.observe(CAMERA, video())
    assert row['current']['age_seconds'] == pytest.approx(1.1)
    assert row['archive']['pending'] == 1
    changed = video()
    changed['frame']['observed_utc'] = '2026-10-29T08:00:01+00:00'
    with pytest.raises(ObservationConflict):
        service.observe(CAMERA, changed)


def test_regression_and_retired_capture_cannot_replace_current(rig):
    service, _, _, _ = rig
    service.observe(CAMERA, video(2))
    with pytest.raises(ObservationConflict):
        service.observe(CAMERA, video(1))
    service.observe(CAMERA, video(1, capture='c' * 32))
    with pytest.raises(ObservationConflict):
        service.observe(CAMERA, video(3))


def test_recent_click_freezes_seen_frame_then_new_revision_replaces_reference(rig):
    service, store, now, _ = rig
    seen = service.snapshot(CAMERA)['cameras'][0]
    now[0] = .04
    latest = service.observe(CAMERA, video(2, x=8))
    saved = service.save_reference(request_reference(seen))['cameras'][0]
    assert saved['reference']['x'] == pytest.approx(6)
    assert saved['reference']['revision'] == 1
    assert saved['current']['x'] == pytest.approx(8)
    saved = service.save_reference(request_reference(latest, expected=1))['cameras'][0]
    assert saved['reference']['x'] == pytest.approx(8) and saved['reference']['revision'] == 2
    assert saved['offset']['inside'] is True
    assert len(store.references) == 2
    with pytest.raises(RevisionConflict):
        service.save_reference(request_reference(latest, expected=0))


def test_reference_rejects_expired_capture_change_or_arbitrary_browser_coordinates(rig):
    service, _, now, _ = rig
    row = service.snapshot(CAMERA)['cameras'][0]
    now[0] = 2.
    with pytest.raises(ObservationConflict):
        service.save_reference(request_reference(row))
    now[0] = .1
    service.observe(CAMERA, video(1, capture='c' * 32))
    with pytest.raises(ObservationConflict):
        service.save_reference(request_reference(row))
    with pytest.raises(ValueError):
        service.save_reference(dict(request_reference(row), x=5))


def test_reference_invalidated_by_processing_and_geometry(rig):
    service, _, _, _ = rig
    row = service.snapshot(CAMERA)['cameras'][0]
    service.save_reference(request_reference(row))
    row = service.observe(CAMERA, video(2, processing='different_processing'))
    assert row['offset'] is None
    row = service.observe(CAMERA, video(3, width=14))
    assert row['offset'] is None


def test_numeric_archive_failure_never_blocks_image_and_reports_overflow():
    store = UnavailableDiagnosticsStore()
    service = DiagnosticsService(lambda name: video(), store, camera_ids=(CAMERA,), archive_capacity=1)
    service.observe(CAMERA, video())
    row = service.observe(CAMERA, video(2))
    assert row['current']['valid'] is True
    assert row['archive']['pending'] == 1 and row['archive']['rejected'] == 1
    assert row['archive']['enabled'] is False
    with pytest.raises(RuntimeError):
        service.save_reference(request_reference(row))


def test_slow_postgres_does_not_hold_frame_analysis_lock(rig):
    service, store, _, _ = rig
    entered, release = threading.Event(), threading.Event()
    original = store.write_observations
    def blocked(records):
        entered.set()
        assert release.wait(3)
        original(records)
    store.write_observations = blocked
    worker = threading.Thread(target=service.drain_once)
    worker.start()
    assert entered.wait(1)
    try:
        started = time.monotonic()
        row = service.observe(CAMERA, video(2))
        assert row['current']['valid'] and time.monotonic() - started < .2
    finally:
        release.set()
        worker.join(3)
    service.drain_once()
    assert len(store.records) == 2
    for record in store.records.values():
        assert not set(record) & {'raw', 'data', 'pixels', 'profiles'}


def calibration(row):
    return dict(commissioned=True, axes=['fake.x', 'fake.y'], pixel_to_steps=[[2., 0.], [0., 3.]],
                gain=.5, max_steps=10, **{name: row[name] for name in
                ('camera_id', 'width', 'height', 'source_kind', 'processing', 'coordinate_space')})


def auto_row(rig):
    service, _, _, _ = rig
    service.save_reference(request_reference(service.snapshot(CAMERA)['cameras'][0], radius=.5))
    service.set_mode(dict(camera_id=CAMERA, expected_revision=0, mode='auto'))
    return service.observe(CAMERA, video(2, x=8, y=6))


class FakeActuator:
    commissioned = True
    def __init__(self):
        self.calls, self.fail = [], False
    def move_relative(self, axis, steps, request_id):
        self.calls.append((axis, steps, request_id))
        if self.fail:
            raise RuntimeError('fake result unknown')


def test_auto_is_blocked_without_calibration_and_default_controller_is_dry_run(rig):
    row = auto_row(rig)
    assert row['planner']['execution_allowed'] is False and row['planner']['state'] == 'BLOCKED'
    motor = FakeActuator()
    controller = CorrectionController(motor)
    assert controller.tick(row, calibration(row))['state'] == 'DRY_RUN'
    assert motor.calls == []


def test_fake_calibrated_controller_rejects_replay_stale_and_fences_unknown_result(rig):
    row = auto_row(rig)
    motor = FakeActuator()
    controller = CorrectionController(motor, live_enabled=True)
    result = controller.tick(row, calibration(row))
    assert result['executed'] is True and [call[1] for call in motor.calls] == [-2, -3]
    assert controller.tick(row, calibration(row))['state'] == 'ALREADY_PROCESSED'
    stale = copy.deepcopy(row)
    stale['sequence'] = 3
    stale['frame_identity'] = stale['frame_identity'].replace('/2/2', '/3/2')
    stale['current']['age_seconds'] = 3.
    assert controller.tick(stale, calibration(stale))['executed'] is False
    newer = rig[0].observe(CAMERA, video(3, x=8, y=6))
    motor.fail = True
    assert controller.tick(newer, calibration(newer))['state'] == 'FAULT'
    assert controller.tick(newer, calibration(newer))['state'] == 'FAULT'
    assert len(motor.calls) == 3


def test_camera_sources_are_independent_and_missing_never_zero_filled(rig):
    service, _, _, _ = rig
    service.register('ni1409:1')
    rows = service.snapshot()['cameras']
    assert [row['channel'] for row in rows] == [1, 2]
    assert rows[0]['current']['x'] is None and rows[0]['current']['quality'] == 'UNAVAILABLE'
    assert rows[1]['current']['x'] == pytest.approx(6)
