"""Dark checkout exercises real transport shape and writers, never hardware."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pytest

from test_v0_andor_commissioning import make_packet
from pump_probe_v0_diagnostic import diagnostic_profile, retain_snapshot, restore_prepared_timing
from pump_probe_v0_tango import decode_tango_batch
from pump_probe_v0_tango_plan import load_profile, validate_profile
from pump_probe_v0_storage import V0TangoRunWriter
from pump_probe_v0_scanplan import ScanPlan

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def dark(tmp_path):
    caps, header_path, payload_path = make_packet(tmp_path, count=2, data_change=lambda data: data.fill(300))
    controller = SimpleNamespace(_hardware_config={'dg645_preflight_policy': 'verify_only'})
    token = retain_snapshot(controller, caps)
    base = load_profile(ROOT / 'web/pump_probe/config/v0_tango_raw_profile.json')
    payload = {'diagnostic_dark': True, 'diagnostic_snapshot_id': token}
    profile = diagnostic_profile(controller, payload, base)
    envelope = json.loads(header_path.read_text())
    return SimpleNamespace(caps=caps, controller=controller, token=token, base=base, payload=payload,
                           profile=profile, header=header_path.read_text(), packet=payload_path.read_bytes(), envelope=envelope)


def test_dark_profile_never_claims_commissioning_and_normal_admission_is_unchanged(dark):
    checked = validate_profile(dark.profile)
    assert checked['commissioned'] is False and checked['diagnostic_dark'] is True
    assert checked['expected_config_fingerprint'] == dark.caps['config_fingerprint']
    assert diagnostic_profile(dark.controller, {}, dark.base) == dark.base
    with pytest.raises(ValueError, match='not commissioned'):
        validate_profile(checked, require_commissioned=True)
    with pytest.raises(ValueError, match='remain uncommissioned'):
        validate_profile({**checked, 'commissioned': True})


@pytest.mark.parametrize('change', [{'diagnostic_dark': 1}, {'diagnostic_dark': True},
                                  {'diagnostic_snapshot_id': 'x'},
                                  {'diagnostic_dark': True, 'diagnostic_snapshot_id': 'wrong'}])
def test_dark_checkout_requires_explicit_boolean_and_matching_snapshot(dark, change):
    with pytest.raises(ValueError):
        diagnostic_profile(dark.controller, change, dark.base)


def test_expired_snapshot_and_changed_camera_are_rejected(dark, monkeypatch):
    import pump_probe_v0_diagnostic as diagnostic
    monkeypatch.setattr(diagnostic.time, 'monotonic', lambda: dark.controller._dark_diagnostic_snapshot[2] + 301)
    with pytest.raises(ValueError, match='Refresh'):
        diagnostic_profile(dark.controller, dark.payload, dark.base)
    bad = deepcopy(dark.caps)
    bad['configuration']['exposure_seconds'] *= 2
    with pytest.raises(ValueError, match='fingerprint'):
        retain_snapshot(dark.controller, bad)


def test_dark_mapping_keeps_native_packets_and_does_not_relax_normal_classifier(dark, tmp_path):
    env = dark.envelope
    args = dict(order_id=env['order_id'], run_id=env['run_id'], point_index=0,
                acquisition_epoch=env['acquisition_epoch'], config_fingerprint=env['config_fingerprint'],
                wavelengths=env['wavelengths'], background_level=560000, cycle_count=2)
    normal = decode_tango_batch((dark.header, dark.packet), **args)
    assert not normal.cycles and len(normal.rejected) == 2
    batch = decode_tango_batch((dark.header, dark.packet), **args, diagnostic_dark=True)
    assert len(batch.cycles) == 2 and not batch.rejected and batch.packet == dark.packet
    assert all(c.metadata['classification']['physical_phases_verified'] is False for c in batch.cycles)
    plan = ScanPlan((0.0, 1.0), (0.0, -.1), 2, 0.0, .1, -10.0, 10.0)
    writer = V0TangoRunWriter(env['wavelengths'], plan.delays, plan.positions, 2, {'tango_profile': dark.profile}, plan=plan)
    for cycle in batch.cycles:
        writer.record_tango_cycle(0, cycle.frames, 0.0, 0.0, cycle.packet, cycle.metadata)
    result = writer.finalize('stopped')
    with h5py.File(result['h5_path'], 'r') as handle:
        assert bool(handle['metadata/diagnostic_dark'][()])
        assert handle['metadata/od_quality'][()].decode() == 'diagnostic_only_not_physical_absorption'
        assert handle['od'].shape == (4, 2)
        assert np.isnan(handle['od'][...]).all()  # Identical dark counts cannot supply I0.
        saved = json.loads(handle['metadata/tango_profile_json'][()])
        assert saved['commissioned'] is False


def test_timing_restore_only_updates_matching_saved_intent(dark, tmp_path, monkeypatch):
    import pump_probe_v0_diagnostic as diagnostic
    monkeypatch.setattr(diagnostic.Path, 'home', classmethod(lambda cls: tmp_path))
    controller = SimpleNamespace(_hardware_config={'andor_device': 'a/b/c', 'dg645_device': 'd/e/f'})
    with pytest.raises(ValueError, match='matching prepared'):
        restore_prepared_timing(controller, dark.caps)
    folder = tmp_path / '.pyconlyse/v0-timing'
    folder.mkdir(parents=True)
    timing = folder / 'timing.json'
    timing.write_text('{}')
    marker = {'camera': 'a/b/c', 'generator': 'd/e/f', 'epoch': dark.caps['acquisition_epoch'],
              'camera_fingerprint': dark.caps['config_fingerprint'], 'timing_path': str(timing)}
    (folder / 'prepared.json').write_text(json.dumps(marker))
    restore_prepared_timing(controller, dark.caps)
    assert controller._hardware_config['dg645_preflight_policy'] == 'verify_only'
    assert controller._hardware_config['dg645_recall_config'] == str(timing)
