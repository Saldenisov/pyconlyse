"""Explicit dark checkout intent, independent from detector commissioning."""
from copy import deepcopy
import json
from pathlib import Path
import time
import uuid

from DeviceServers.cameras.andor.v0_orders import config_fingerprint

CLASSIFIER = 'v0-dark-sequential-test-v1'
SNAPSHOT_TTL_S = 300


def restore_prepared_timing(controller, caps):
    """Recover only saved intent after Web restart; never send DG645 writes."""
    hardware = controller._hardware_config
    if hardware.get('dg645_preflight_policy') == 'verify_only':
        return
    folder = Path.home() / '.pyconlyse' / 'v0-timing'
    try:
        marker = json.loads((folder / 'prepared.json').read_text(encoding='utf-8'))
        timing = Path(marker['timing_path'])
        valid = (marker['camera'].lower() == hardware['andor_device'].lower()
                 and marker['generator'].lower() == hardware['dg645_device'].lower()
                 and marker['epoch'] == caps['acquisition_epoch']
                 and marker['camera_fingerprint'] == caps['config_fingerprint']
                 and timing.resolve().parent == folder.resolve() and timing.is_file())
    except (OSError, ValueError, KeyError, TypeError):
        valid = False
    if not valid:
        raise ValueError('Dark checkout needs a matching prepared DG645 timing snapshot; generator retained')
    hardware.update(dg645_recall_config=str(timing), dg645_preflight_policy='verify_only')


def retain_snapshot(controller, capabilities):
    caps = deepcopy(capabilities)
    if not all(caps.get(k) is True for k in (
            'configuration_fresh', 'external_trigger', 'acquisition_active', 'lossless')):
        raise ValueError('Dark checkout requires an armed, fresh, lossless external-trigger camera')
    if caps.get('track_count') != 2 or not caps.get('acquisition_epoch'):
        raise ValueError('Dark checkout requires two detector tracks and an acquisition epoch')
    if config_fingerprint(caps['configuration']) != caps.get('config_fingerprint'):
        raise ValueError('Dark checkout camera configuration fingerprint is inconsistent')
    restore_prepared_timing(controller, caps)
    token = uuid.uuid4().hex
    controller._dark_diagnostic_snapshot = (token, caps, time.monotonic())
    return token


def diagnostic_profile(controller, payload, original):
    enabled = payload.get('diagnostic_dark', False)
    if type(enabled) is not bool:
        raise ValueError('diagnostic_dark must be boolean')
    if not enabled:
        if 'diagnostic_snapshot_id' in payload:
            raise ValueError('A diagnostic snapshot requires explicit dark checkout')
        return original
    snapshot = getattr(controller, '_dark_diagnostic_snapshot', None)
    if (snapshot is None or payload.get('diagnostic_snapshot_id') != snapshot[0]
            or not 0 <= time.monotonic() - snapshot[2] <= SNAPSHOT_TTL_S):
        raise ValueError('Refresh the dark checkout camera snapshot before starting')
    caps = snapshot[1]
    profile = deepcopy(original)
    profile.update(
        diagnostic_dark=True, commissioned=False,
        commissioning_status='Diagnostic dark checkout only; not detector commissioning or physical absorption',
        profile_version='v0-dark-checkout-v1', classifier_version=CLASSIFIER,
        expected_config_fingerprint=caps['config_fingerprint'], expected_sample_dtype=None,
        diagnostic_configuration=caps['configuration'], all_cycles=True,
        filters={'version': 'trancon-detector-filters-v1', 'repump': {'enabled': False},
                 'nonfinite': {'enabled': False}, 'similarity': {'enabled': False}},
    )
    return profile
