"""An Andor order must contain complete signal/reference pairs."""
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

BACKEND = Path(__file__).resolve().parents[2] / 'web' / 'backend'
sys.path.insert(0, str(BACKEND))
import pump_probe_v0_api as api


def decode(values, width, monkeypatch):
    monkeypatch.setattr(api, '_tango_proxy', lambda *_a, **_k: pytest.fail('Decoder must not access devices'))
    controller = api.PumpProbeV0Controller()
    payload = repr(zlib.compress(np.asarray(values, dtype=np.float32).tobytes()))
    return controller._decode_andor_order_locked(payload, width)


@pytest.mark.parametrize('values,width', [
    ([500, 11, 22, 99], 1),
    ([500, 600, 11, 12, 21, 22, 91, 92], 2),
])
def test_orphan_track_is_rejected_instead_of_discarded(values, width, monkeypatch):
    with pytest.raises(ValueError, match='incomplete signal/reference pair'):
        decode(values, width, monkeypatch)


def test_one_complete_pair_keeps_values_and_axis(monkeypatch):
    axis, tracks = decode([500, 11, 22], 1, monkeypatch)
    np.testing.assert_array_equal(axis, [500])
    np.testing.assert_array_equal(tracks, [[[11], [22]]])


def test_multiple_pairs_keep_shot_track_and_pixel_order(monkeypatch):
    axis, tracks = decode([500, 600, 11, 12, 21, 22, 31, 32, 41, 42], 2, monkeypatch)
    np.testing.assert_array_equal(axis, [500, 600])
    np.testing.assert_array_equal(tracks, [[[11, 12], [21, 22]], [[31, 32], [41, 42]]])
