"""Decoder and Tango orchestration checks using only local fake proxies."""

import hashlib
import json
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))

from pump_probe_v0_tango import (
    AcquisitionCancelled, PACKET_SCHEMA, RejectedCycle, TangoPacketError,
    TangoRawAdapter, classify_trancon_cycle, decode_tango_batch, decode_tango_cycle,
)


WAVES = [500., 600.]
CONTEXT = {"order_id": "order-1", "run_id": "run-1", "point_index": 0,
           "acquisition_epoch": "epoch-1", "config_fingerprint": "config-1",
           "wavelengths": WAVES, "background_level": 1}


def triplet(background=0):
    result = np.array([[[10, 11], [2, 3]], [[20, 21], [4, 5]],
                       [[30, 31], [6, 7]]], dtype=np.float32)
    result[background, 1] = 0
    return result


def encoded(data=None, *, sample_dtype="<f4", **overrides):
    data = triplet() if data is None else np.asarray(data)
    samples = data.astype(sample_dtype).tobytes(order="C")
    count = len(data)
    header = {"schema": PACKET_SCHEMA, **{k: CONTEXT[k] for k in (
        "order_id", "run_id", "point_index", "acquisition_epoch", "config_fingerprint")},
        "state": "complete", "armed": True, "dtype": sample_dtype, "array_order": "C",
        "compression": "zlib", "phase_labels": None, "track_order": ["detector_I", "detector_II"],
        "wavelengths": WAVES, "frame_count": count, "frames_captured": count,
        "shape": [count, 2, 2], "frame_ids": list(range(100, 100+count)),
        "boundary_frame_id": 100, "payload_sha256": hashlib.sha256(samples).hexdigest(),
        "host_receive_times": ["host-only"] * count, **overrides}
    return json.dumps(header), zlib.compress(samples)


@pytest.mark.parametrize("g", [0, 1, 2])
def test_background_II_anchor_preserves_both_detector_phase_maps_and_raw(g):
    data = triplet(g)
    before = data.copy()
    groups, details = classify_trancon_cycle(data, 1)
    mapping = {"BG": g, "Ie": (g+2) % 3, "I0": (g+1) % 3}
    assert details["phase_mapping"] == {"detector_I": mapping, "detector_II": mapping}
    np.testing.assert_array_equal(groups, [data[g, 0], data[g, 1], data[mapping["Ie"], 0],
                                         data[mapping["Ie"], 1], data[mapping["I0"], 0], data[mapping["I0"], 1]])
    groups[0, 0] = 999
    np.testing.assert_array_equal(data, before)


def test_exact_threshold_is_strict_and_ambiguity_rejects_whole_cycle():
    data = triplet()
    data[0, 1] = [.5, .5]  # SUM(SGL)==1 is not less than BG_level=1.
    with pytest.raises(RejectedCycle) as raised:
        classify_trancon_cycle(data, 1, False)
    assert raised.value.metadata["classification"]["background_candidates"] == []
    data[:2, 1] = 0
    with pytest.raises(RejectedCycle) as raised:
        classify_trancon_cycle(data, 1, False)
    assert raised.value.metadata["classification"]["background_candidates"] == [0, 1]
    assert raised.value.metadata["classification"]["invalid_triplet_policy"] == "reject_whole_physical_cycle"


def test_all_true_source_fallback_uses_II_g1_but_I_g0():
    data = triplet()
    data[:, 1] = [[2, 3], [4, 5], [6, 7]]
    groups, detail = classify_trancon_cycle(data, 1, True)
    assert detail["source_fallback_quirk"] is True
    assert detail["phase_mapping"] == {"detector_I": {"BG": 0, "Ie": 2, "I0": 1},
                                       "detector_II": {"BG": 1, "Ie": 0, "I0": 2}}
    np.testing.assert_array_equal(groups, [data[0, 0], data[1, 1], data[2, 0],
                                         data[0, 1], data[1, 0], data[2, 1]])


def test_batch_preserves_original_packet_and_full_header_with_per_triplet_subsets():
    raw = np.concatenate([triplet(0), triplet(2)])
    transport = encoded(raw)
    batch = decode_tango_batch(transport, **CONTEXT, cycle_count=2)
    assert len(batch.cycles) == 2 and not batch.rejected
    assert batch.packet == transport[1]
    for index, cycle in enumerate(batch.cycles):
        assert cycle.packet == transport[1]
        assert cycle.metadata["source_envelope"] == json.loads(transport[0])
        assert cycle.metadata["packet_cycle_index"] == index
        assert cycle.metadata["frame_indices"] == list(range(100+index*3, 103+index*3))
        assert cycle.metadata["packet_sha256"] == hashlib.sha256(transport[1]).hexdigest()
        assert cycle.frames.dtype == np.float32
    # A rejected triplet cannot shift the surviving detector sequences.
    raw[:3, 1] = 2
    batch = decode_tango_batch(encoded(raw), **CONTEXT, cycle_count=2)
    assert len(batch.cycles) == len(batch.rejected) == 1
    assert batch.cycles[0].metadata["packet_cycle_index"] == 1
    assert batch.rejected[0].metadata["packet_cycle_index"] == 0


@pytest.mark.parametrize("change", [
    {"schema": "unknown-v2"}, {"dtype": ">f4"}, {"shape": [3, 1, 2]},
    {"array_order": "F"}, {"compression": "raw"}, {"payload_sha256": "0"*64},
    {"frame_ids": [100, 102, 103]}, {"frame_ids": [True, 101, 102]},
    {"boundary_frame_id": 99}, {"acquisition_epoch": "old"}, {"config_fingerprint": "old"},
    {"point_index": True}, {"wavelengths": [500., float(np.nextafter(600., 601.))]},
    {"phase_labels": ["BG", "I0", "Ie"]}, {"track_order": ["detector_II", "detector_I"]},
    {"state": "cancelled"}, {"armed": False},
])
def test_decoder_rejects_stale_corrupt_or_unsupported_envelope_and_keeps_bytes(change):
    transport = encoded(**change)
    with pytest.raises(TangoPacketError) as raised:
        decode_tango_cycle(transport, **CONTEXT)
    assert raised.value.packet == transport[1]
    assert raised.value.metadata["raw_header"] == transport[0]


@pytest.mark.parametrize("corrupt", ["trailing", "truncated", "nonfinite"])
def test_decoder_rejects_payload_corruption_without_losing_original_bytes(corrupt):
    if corrupt == "nonfinite":
        raw = triplet()
        raw[0, 0, 0] = np.inf
        header, packet = encoded(raw)
    else:
        header, packet = encoded()
        packet = packet + b"trailing" if corrupt == "trailing" else packet[:-2]
    with pytest.raises(TangoPacketError) as raised:
        decode_tango_cycle((header, packet), **CONTEXT)
    assert raised.value.packet == packet


@pytest.mark.parametrize("dtype", ["<u2", "<i4"])
def test_integer_payload_retains_exact_packet_and_discloses_sgl_canonicalization(dtype):
    raw = triplet().astype(dtype)
    if dtype == "<i4":
        raw[1, 0, 0] = 2**24 + 1
    transport = encoded(raw, sample_dtype=dtype)
    result = decode_tango_cycle(transport, **CONTEXT)
    assert result.packet == transport[1]
    restored = np.frombuffer(zlib.decompress(result.packet), dtype=dtype).reshape(raw.shape)
    np.testing.assert_array_equal(restored, raw)
    assert result.frames.dtype == np.float32
    assert result.metadata["source_sample_dtype"] == dtype
    assert result.metadata["canonical_sample_dtype"] == "<f4"
    assert result.metadata["samples_rounded_to_sgl"] is (dtype == "<i4")
    if dtype == "<i4":
        # I0I is physical frame1; exact 16777217 persists only in original packet.
        assert int(result.frames[4, 0]) == 2**24
        assert int(restored[1, 0, 0]) == 2**24 + 1


class FakeClock:
    now = 0.
    def __call__(self):
        return self.now


class FakeStop:
    def __init__(self, clock):
        self.clock, self.cancelled = clock, False
    def is_set(self):
        return self.cancelled
    def set(self):
        self.cancelled = True
    def wait(self, seconds):
        self.clock.now += max(seconds, .01)
        return self.cancelled


class FakeCamera:
    def __init__(self, log, active=False):
        self.log, self.active = log, active
        self.statuses = ["queued", "capturing", "complete"]
        self.packet_override, self.on_read = None, None
        self.fail_begin_once = False
        self.request = None
    def state(self):
        return "ON"
    def command_inout(self, name, argument=None):
        self.log.append(("camera", name, argument))
        if name == "V0Capabilities":
            return {"schema": PACKET_SCHEMA, "track_count": 2, "external_trigger": True,
                    "configuration_fresh": True, "lossless": self.active, "acquisition_active": self.active,
                    "config_fingerprint": "config-1", "acquisition_epoch": "epoch-1",
                    "width": 2, "wavelengths": WAVES}
        if name == "start_grabbing":
            self.active = True
        elif name == "V0BeginOrder":
            request = json.loads(argument)
            if self.request is not None:
                assert request == self.request  # Retry preserves idempotency content.
            self.request = request
            if self.fail_begin_once:
                self.fail_begin_once = False
                raise TimeoutError("reply lost")
            return {"order_id": "order-1"}
        elif name == "V0OrderStatus":
            state = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return {"order_id": "order-1", "state": state}
        elif name == "V0ReadOrder":
            if self.on_read:
                self.on_read()
            if self.packet_override:
                return self.packet_override
            cycles = self.request["frame_count"] // 3
            return encoded(np.concatenate([triplet()] * cycles))
        elif name in {"V0CancelOrder", "V0ReleaseOrder", "stop_grabbing"}:
            return None
        else:
            raise AssertionError("Unexpected camera command " + name)


class FakeStage:
    def __init__(self, log):
        self.log, self.target = log, 0.
        self.position_reads = 0
        self.status = "ON"
    def command_inout(self, name, argument):
        self.log.append(("stage", name, argument))
        if name == "move_axis":
            self.target = argument[1]
        else:
            assert name == "stop_axis"
    def read_attribute(self, name):
        if name == "positions":
            self.position_reads += 1
            return SimpleNamespace(value={3: self.target})
        return SimpleNamespace(value={3: self.status})


class FakeDG:
    def __init__(self, log):
        self.log = log
    def command_inout(self, name, argument):
        self.log.append(("dg", name, argument))
        assert name == "scpi_query" and argument == "BURC?"
        return "3"


def adapter(active=False):
    log, clock = [], FakeClock()
    stop = FakeStop(clock)
    camera, stage, dg = FakeCamera(log, active), FakeStage(log), FakeDG(log)
    intent = SimpleNamespace(profile={"expected_config_fingerprint": "config-1", "poll_interval_s": .1,
        "move_timeout_s": 1., "move_tolerance_mm": .01, "settled_samples": 2,
        "order_timeout_s": 1., "background_level": 1, "all_cycles": False},
        hardware_config={"andor_device": "camera", "owis_aggregator_device": "stage",
                         "dg645_device": "dg", "delay_line_axis": 3, "dg645_preflight_policy": "verify_only"},
        scan_plan=SimpleNamespace(positions=(0., -1.)),
        dg645_recall={"snapshot": {"raw_queries": {"BURC?": "3"}}})
    proxies = {"camera": camera, "stage": stage, "dg": dg}
    factory = lambda name, **_kwargs: proxies[name]
    value = TangoRawAdapter(intent, factory, stop, monotonic=clock)
    return value, camera, stage, stop, log


def commands(log, name):
    return [entry for entry in log if entry[1] == name]


def test_adapter_move_settle_batch_decode_then_explicit_ack_without_phase_commands():
    value, camera, stage, stop, log = adapter()
    np.testing.assert_array_equal(value.open(), WAVES)
    assert value.move_to(0) == 0
    assert stage.position_reads == 2
    batch = value.acquire_batch("run-1", 0, 2)
    assert len(batch.cycles) == 2
    assert camera.request["frame_count"] == 6
    assert not commands(log, "V0ReleaseOrder")
    assert value.pending_order == "order-1"
    with pytest.raises(RuntimeError, match="acknowledge"):
        value.acquire_cycle("run-1", 0)
    # Caller has now committed every accepted/rejected slot and fsynced journal.
    value.acknowledge_cycle()
    assert len(commands(log, "V0ReleaseOrder")) == 1
    assert value.pending_order is None
    value.close()
    assert len(commands(log, "start_grabbing")) == len(commands(log, "stop_grabbing")) == 1
    assert len(commands(log, "move_axis")) == len(commands(log, "stop_axis")) == 1
    assert [item[1] for item in log if item[0] == "dg"] == ["scpi_query"]


@pytest.mark.parametrize("failure", ["timeout", "decode", "cancel"])
def test_failed_or_cancelled_order_keeps_partial_packet_until_durable_ack(failure):
    value, camera, stage, stop, log = adapter()
    value.open()
    value.move_to(0)
    if failure == "timeout":
        camera.statuses = ["capturing"]
        expected = TimeoutError
    elif failure == "decode":
        camera.packet_override = encoded(payload_sha256="f" * 64)
        expected = TangoPacketError
    else:
        def cancel_on_order(_order):
            stop.set()
        value.on_order = cancel_on_order
        expected = AcquisitionCancelled
    with pytest.raises(expected):
        value.acquire_cycle("run-1", 0)
    assert value.pending_order == "order-1"
    assert not commands(log, "V0ReleaseOrder")
    packet, meta = value.close()
    assert packet and meta["source_order_id"] == "order-1"
    assert value.pending_order == "order-1"
    assert not commands(log, "V0ReleaseOrder")
    # After rejected-transport persistence + fsync, cleanup release is explicit.
    value.acknowledge_cycle()
    assert len(commands(log, "V0ReleaseOrder")) == 1


def test_uncertain_begin_reply_cleanup_reuses_request_before_partial_journal():
    value, camera, stage, stop, log = adapter()
    value.open()
    camera.fail_begin_once = True
    with pytest.raises(TimeoutError, match="reply lost"):
        value.acquire_cycle("run-1", 0)
    assert value.pending_order is None and value.pending_request
    assert value.close()[0]
    attempts = commands(log, "V0BeginOrder")
    assert len(attempts) == 2 and attempts[0][2] == attempts[1][2]
    assert not commands(log, "V0ReleaseOrder")
    value.acknowledge_cycle()


def test_adapter_leaves_preexisting_camera_running_and_rejects_faulted_stage():
    value, camera, stage, stop, log = adapter(active=True)
    value.open()
    stage.status = "FAULT"
    with pytest.raises(ValueError, match="not ready"):
        value.move_to(0)
    value.close()
    assert not commands(log, "start_grabbing") and not commands(log, "stop_grabbing")
    assert not commands(log, "V0BeginOrder")
    assert commands(log, "stop_axis")


def test_camera_configuration_drift_fails_before_any_order():
    value, camera, stage, stop, log = adapter()
    value.profile["expected_config_fingerprint"] = "different-profile"
    with pytest.raises(ValueError, match="commissioned detector profile"):
        value.open()
    value.close()
    assert not commands(log, "V0BeginOrder")


@pytest.mark.parametrize("late", ["cancel", "deadline"])
def test_reply_returning_after_cancellation_or_deadline_never_returns_usable_batch(late):
    value, camera, stage, stop, log = adapter()
    value.open()
    camera.statuses = ["complete"]
    if late == "cancel":
        camera.on_read = stop.set
        expected = AcquisitionCancelled
    else:
        camera.on_read = lambda: setattr(stop.clock, "now", stop.clock.now + 2.)
        expected = TimeoutError
    with pytest.raises(expected):
        value.acquire_batch("run-1", 0)
    assert not commands(log, "V0ReleaseOrder")
    assert value.pending_order == "order-1"
    assert value.close()[0]
