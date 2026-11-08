"""Strict camera projection boundary without importing an XP control runtime.

The portable XP wire validator has the same contract; parity is tested with
both native and LabVIEW frames. No device, Tango or database dependency.
"""
import base64
import datetime
import math
import re

MAX_RAW = 524288
SESSION = re.compile(r'^[0-9a-f]{32}$')


def validate_video_frame(value):
    fields = {'source', 'simulated', 'sequence', 'sequence_interpretation', 'capture_session_id',
        'observed_utc', 'sample_elapsed_seconds', 'width', 'height', 'pixel_type', 'encoding',
        'data', 'channel', 'processing', 'hardware_acknowledged', 'source_age_seconds'}
    bridge = isinstance(value, dict) and value.get('source') == 'labview_supervision_ni1409'
    if bridge:
        fields.add('source_session_id')
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Exact independently identified camera frame required')
    session = lambda item: type(item) is str and SESSION.fullmatch(item) is not None
    age = lambda item: type(item) in (int, float) and math.isfinite(item) and item >= 0
    if (value['source'] not in ('python_supervision_ni1409', 'labview_supervision_ni1409')
            or bridge and not session(value['source_session_id']) or not session(value['capture_session_id'])
            or value['simulated'] is not False or value['hardware_acknowledged'] is not False
            or type(value['sequence']) is not int or not 1 <= value['sequence'] <= 2**53 - 1
            or value['sequence_interpretation'] != 'software grab observation, not hardware frame counter'
            or not age(value['sample_elapsed_seconds']) or not age(value['source_age_seconds'])
            or type(value['width']) is not int or type(value['height']) is not int
            or not 1 <= value['width'] <= MAX_RAW or not 1 <= value['height'] <= MAX_RAW
            or value['width'] * value['height'] > MAX_RAW or value['pixel_type'] != 'U8'
            or value['encoding'] != 'base64_raw_row_major' or type(value['channel']) is not int
            or not 0 <= value['channel'] <= 0xFFFFFFFF
            or value['processing'] != 'raw_grab_before_legacy_interlace_bcg_profiles'
            or type(value['observed_utc']) is not str or len(value['observed_utc']) > 40
            or not value['observed_utc'].endswith('+00:00') or type(value['data']) is not str
            or len(value['data']) > 4 * ((MAX_RAW + 2) // 3)):
        raise ValueError('Invalid bounded raw U8 camera metadata')
    raw = base64.b64decode(value['data'].encode('ascii'), validate=True)
    datetime.datetime.strptime(value['observed_utc'][:-6],
        '%Y-%m-%dT%H:%M:%S.%f' if '.' in value['observed_utc'] else '%Y-%m-%dT%H:%M:%S')
    if len(raw) != value['width'] * value['height']:
        raise ValueError('Camera pixels do not match geometry')
