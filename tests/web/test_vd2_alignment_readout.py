import base64
import json
import math
import time

import pytest

from tests.web.test_vd2_alignment import client, vd2
from vd2_alignment_readout import AlignmentReadout


ROI = {"wavelengthMin": 500, "wavelengthMax": 700, "topPercent": 0, "bottomPercent": 100}
WINDOWS = {"baseline": [0, 9], "signal": [12, 16]}
BASE = "/api/pump-probe-vd2"


def frame(name, drop=20, **changes):
    # Two wavelength channels see the same rise; only the first sees the drop.
    pixels = bytes(100 + i - (drop if i >= 12 and col == 0 else 0)
                   for i in range(32) for col in range(2))
    return dict(width=2, height=32, received_at=name, pixels_b64=base64.b64encode(pixels).decode(),
                stream_state="acquiring", calibration_key="axes", measurement_key="gain",
                calibration={"width": 2, "height": 32, "time_unit": "ns",
                             "wavelengths": [550, 650], "timedelays": list(range(32))}) | changes


@pytest.fixture
def source(monkeypatch):
    source = AlignmentReadout()
    monkeypatch.setattr(vd2, "_alignment_readout", source)
    monkeypatch.setattr(vd2, "_protocol_hardware_phase", lambda: "acquiring")
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("readout must not contact camera"))
    monkeypatch.setattr(vd2, "DeviceProxy", lambda *_: pytest.fail("readout must not contact Tango"))
    return source


def query(viewer, name, region=ROI, windows=WINDOWS):
    return viewer.get(BASE + "/alignment/readout",
                      query_string={"frame": name, "selection": json.dumps({"region": region, "windows": windows})})


def test_windows_share_one_stream_but_choose_independent_roi_and_cursors(source):
    epoch = math.floor(time.monotonic())
    source.observe(frame("one", 20), epoch - .65)
    source.observe(frame("two", 40), epoch - .30)
    source.observe(frame("anchor", 60), epoch + .01)
    first, second = client(), client()  # same client address; independent geometry
    a = query(first, "anchor").json
    b = query(second, "anchor").json
    for key in ("profile", "comparison", "summary", "signal_key"):
        assert a[key] == b[key]
    assert a["comparison"]["percent"] == pytest.approx(100 * 30 / 114)
    assert a["comparison"]["optical_density"] == pytest.approx(math.log10(114 / 84))
    assert a["summary"]["mean"] == pytest.approx(100 * 15 / 114)
    assert a["summary"]["sd"] == pytest.approx(100 * math.sqrt(50) / 114)
    assert a["summary"]["n"] == 2
    other_roi = query(second, "anchor", ROI | {"wavelengthMin": 600}).json
    assert other_roi["comparison"]["found"] and other_roi["summary"]["mean"] == 0
    assert other_roi["comparison"]["optical_density"] == 0
    other_cursors = query(second, "anchor", windows={"baseline": [0, 5], "signal": [7, 10]}).json
    assert other_cursors["comparison"]["percent"] == 0
    assert query(first, "anchor").json["summary"] == a["summary"]


def test_zero_signal_keeps_the_relative_drop_but_has_no_finite_optical_density(source):
    pixels = bytes(100 if i < 12 else 0 for i in range(32) for _ in range(2))
    source.observe(frame("zero", pixels_b64=base64.b64encode(pixels).decode()), time.monotonic())
    comparison = query(client(), "zero").json["comparison"]
    assert comparison["found"] and comparison["percent"] == 100
    assert comparison["optical_density"] is None


def test_invalid_windows_report_reason_and_auto_windows_follow_edge(source):
    source.observe(frame("anchor"), time.monotonic())
    viewer = client()
    bad = query(viewer, "anchor", windows={"baseline": [0, 1], "signal": [12, 16]}).json
    assert not bad["comparison"]["found"] and bad["summary"] is None
    assert bad["comparison"]["error"] == "Each window needs at least 3 points."
    auto = query(viewer, "anchor", windows=None).json
    assert auto["windows"] == {"baseline": [2, 11], "signal": [12, 16]}
    assert auto["comparison"]["percent"] == pytest.approx(100 * 10 / 114)
    assert query(viewer, "anchor", ROI | {"topPercent": True}).status_code == 422


def test_stream_loss_and_gain_changes_cannot_reuse_live_samples(source, monkeypatch):
    epoch = math.floor(time.monotonic())
    source.observe(frame("previous"), epoch - .15)
    source.observe(frame("first"), epoch + .01)
    assert query(client(), "first").json["summary"]["kind"] == "mean"
    source.unavailable()
    lost = query(client(), "first").json
    assert not lost["fresh"]
    source.observe(frame("recovered", measurement_key="other gain"), epoch + .2)
    current = query(client(), "recovered").json
    assert current["signal_key"] != lost["signal_key"]
    assert current["summary"]["kind"] == "frame"
    monkeypatch.setattr(vd2, "_protocol_hardware_phase", lambda: "saving")
    assert not query(client(), "recovered").json["fresh"]


def test_frame_timestamp_not_renewed_by_polling_or_roi_edits(source):
    source.observe(frame("stale"), time.monotonic() - 3)
    a = query(client(), "stale").json
    b = query(client(), "stale", ROI | {"wavelengthMin": 600}).json
    assert not a["fresh"] and not b["fresh"] and b["frame_age_ms"] >= a["frame_age_ms"] >= 3000
    assert query(client(), "evicted").status_code == 404
    capability = client().get(BASE + "/alignment/readout?capabilities=1")
    assert capability.json == {"success": True, "version": 1}
    assert capability.headers["Cache-Control"] == "no-store"


def test_preview_publishes_shared_frame_and_readout_never_reads_it_again(source, monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(state=lambda: "ON",
                           read_attribute=lambda key: SimpleNamespace(value=True if key == "application_running" else "busy"))
    original = frame("ignored")
    reads = []
    def read_pixels(_):
        reads.append(True)
        return {k: original[k] for k in ("width", "height", "pixels_b64")}
    monkeypatch.setattr(vd2, "_preview_cache", None)
    monkeypatch.setattr(vd2, "_preview_cache_until", 0.0)
    monkeypatch.setattr(vd2, "_preview_period", 10)
    monkeypatch.setattr(vd2, "_proxy", lambda: fake)
    monkeypatch.setattr(vd2, "_read_display_frame", read_pixels)
    monkeypatch.setattr(vd2, "_alignment_frame_metadata", lambda _: ({}, {}))
    monkeypatch.setattr(vd2, "_alignment_axes", original["calibration"] | {"settings": {}})
    one, two = client(), client()
    frame_id = one.get(BASE + "/preview").json["received_at"]
    assert two.get(BASE + "/preview").json["received_at"] == frame_id
    monkeypatch.setattr(vd2, "_proxy", lambda: pytest.fail("readout must not contact camera"))
    assert query(one, frame_id).json["comparison"] == query(two, frame_id).json["comparison"]
    assert len(reads) == 1
