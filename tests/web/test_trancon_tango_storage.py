"""Offline detector-paired RAW/transport persistence and resume contracts."""

import hashlib
import json
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "web/backend"))

from pump_probe_v0_dataset import load_payload, read_dataset, treat_dataset
from pump_probe_v0_processing import (
    TRANCON_FLOAT_LAYOUT, TRANCON_GROUPS, TRANCON_LAYOUT, calculate_raw_od,
)
from pump_probe_v0_scanplan import build_scan_plan
from pump_probe_v0_storage import V0EmulatorRunWriter, V0TangoRunWriter


def plan(shots=2):
    return build_scan_plan({"delay_points_ps": [0., 2., 0.], "pulses_per_point": shots,
                            "real_zero_ps": 0., "calibration_version": "fixture-v1"}, .5, -2., 2.)


def config():
    return {"tango_profile": {"schema": "fixture-camera-v1", "camera": "mock/andor/1",
                              "track_mapping": {"I": 0, "II": 1}, "calibration": "fixture-v1"}}


def frames(ratio=1.):
    # Unequal measured backgrounds + fractional/summed counts cannot be U16.
    return np.array([[10.25, 70000.5], [90.5, 80000.25],
                     [110.25, 70100.5], [190.5, 80100.25],
                     [10.25 + 100 * ratio, 70000.5 + 100 * ratio],
                     [190.5, 80100.25]], dtype=np.float32)


def metadata(index=0, **changes):
    return {"source_order_id": f"order-{index}", "frame_indices": [10, 11, 12],
            "acquisition_epoch": "epoch-1", "config_fingerprint": "fixture-config-hash",
            "track_order": ["detector_I", "detector_II"],
            "phase_mapping": {name: {"BG": 0, "Ie": 1, "I0": 2}
                              for name in ("detector_I", "detector_II")},
            "source_envelope": {"schema": "andor-v0-raw-order-v1", "frame_ids": [10, 11, 12],
                                "payload_sha256": "fixture-uncompressed-sha"}, **changes}


@pytest.fixture
def writer():
    intent = plan()
    value = V0TangoRunWriter([500., 600.], intent.delays, intent.positions, 2,
                             config(), plan=intent)
    yield value
    if not value._closed:
        value.finalize("stopped")


def record(writer, values, packet=b"\x00original\xff", point=0, meta=None):
    return writer.record_tango_cycle(point, values, writer.positions[point],
                                    writer.positions[point] + .001, packet, metadata() if meta is None else meta)


def envelope(record):
    return json.loads(record["envelope_json"].asstr()[()])


def test_float32_detector_formula_is_mean_of_shot_logs_not_log_of_mean(writer):
    first, second = frames(1.), frames(9.)
    original = first.copy()
    np.testing.assert_allclose(record(writer, first), 0., atol=1e-15)
    np.testing.assert_allclose(record(writer, second, b"second"), np.log10(9) / 2, atol=1e-15)
    result = writer.finalize()
    with h5py.File(result["h5_path"], "r") as handle:
        assert handle["raw_data"].dtype == np.float32
        assert tuple(handle["raw_group_names"].asstr()[...]) == TRANCON_GROUPS
        assert handle["metadata/raw_layout"].asstr()[()] == TRANCON_FLOAT_LAYOUT
        np.testing.assert_array_equal(handle["raw_data"][0, :, 0], original)
        np.testing.assert_array_equal(handle["raw_data"][0, :, 1], second)
        np.testing.assert_allclose(handle["od"][:, 0], np.log10(9) / 2, atol=1e-15)
        wrong = np.log10(5.)
        assert abs(handle["od"][0, 0] - wrong) > .1
    payload = Path(result["h5_path"]).read_bytes()
    dataset, _ = read_dataset("tango.h5", payload)
    assert dataset.layout == TRANCON_FLOAT_LAYOUT
    assert dataset.blocks[0].dtype == np.float32 and not dataset.blocks[0].flags.writeable
    preview = load_payload("tango.h5", payload)
    assert {"raw_od", "raw_background"}.issubset(preview["capabilities"])
    recalculated, response = treat_dataset("tango.h5", payload, [{"kind": "raw_od"}],
                                           hashlib.sha256(payload).hexdigest())
    np.testing.assert_array_equal(recalculated.od, dataset.od)
    assert response["frame_counts"] == [2, 0, 0]
    assert response["shot_selection"]["source_used_counts"] == [2, 0, 0]


def test_signed_infinity_and_nan_survive_storage_and_reload(writer):
    values = np.array([[0, 0], [0, 0], [0, 1], [1, 1], [1, 0], [1, 1]], dtype=np.float32)
    assert record(writer, values) == [None, None]
    record(writer, values, b"next")
    result = writer.finalize("stopped")
    with h5py.File(result["h5_path"]) as handle:
        assert np.isposinf(handle["od"][0, 0]) and np.isneginf(handle["od"][1, 0])
        np.testing.assert_array_equal(handle["raw_data"][0, :, 0], values)
    values[2, :] = 0
    values[4, :] = 0
    calculated, _, _ = calculate_raw_od([values[:, None, :]], TRANCON_FLOAT_LAYOUT)
    assert np.isnan(calculated).all()


def test_transport_bytes_and_metadata_detach_from_mutable_caller(writer):
    packet = bytearray(b"\x00\xff\x80wire")
    expected = bytes(packet)
    meta = metadata()
    record(writer, frames(), packet, meta=meta)
    packet[0] = 44
    meta["frame_indices"][0] = 999
    item = writer._h5["transport/accepted/00000000"]
    assert item["packet"][...].tobytes() == expected
    stored = envelope(item)
    assert stored["packet_sha256"] == hashlib.sha256(expected).hexdigest()
    assert stored["metadata"]["frame_indices"] == [10, 11, 12]
    assert stored["raw_slot"] == {"delay_index": 0, "shot_index": 0}
    assert stored["readback_position_mm"] == .001
    assert stored["scan_plan_fingerprint"] == writer.plan.fingerprint


@pytest.mark.parametrize("case", ["shape", "nonfinite", "rounding", "hash", "metadata", "target", "order", "empty"])
def test_invalid_cycle_preserves_raw_counts_and_sums_and_archives_rejected_packet(writer, case):
    values, packet, meta = frames(), b"bad-wire", metadata()
    target, point = writer.positions[0], 0
    if case == "shape":
        values = values[:5]
    elif case == "nonfinite":
        values[0, 0] = np.inf
    elif case == "rounding":
        values = values.astype(np.float64)
        values[0, 0] = .1
    elif case == "hash":
        meta["packet_sha256"] = "f" * 64
    elif case == "metadata":
        meta["bad"] = float("nan")
    elif case == "target":
        target += 1
    elif case == "order":
        point = 1
    elif case == "empty":
        packet = b""
    before_sum, before_od = writer._sums.copy(), writer._od_sums.copy()
    with pytest.raises(ValueError):
        writer.record_tango_cycle(point, values, target, target, packet, meta)
    assert writer.artifacts()["frame_counts"] == [0, 0, 0]
    np.testing.assert_array_equal(writer._sums, before_sum)
    np.testing.assert_array_equal(writer._od_sums, before_od)
    assert np.isnan(writer._h5["raw_data"][...]).all()
    assert len(writer._h5["transport/accepted"]) == 0
    rejected = writer._h5["transport/rejected/00000000"]
    assert rejected["packet"][...].tobytes() == packet
    assert envelope(rejected)["raw_slot"] is None


def test_incomplete_or_aborted_transport_never_advances_raw(writer):
    item = writer.record_rejected_transport(b"partial", {"source_order_id": "late", "phase": "Ie"}, "aborted")
    assert item["reason"] == "aborted"
    assert writer.artifacts()["frame_counts"] == [0, 0, 0]
    record(writer, frames())
    assert writer.artifacts()["frame_counts"] == [1, 0, 0]
    assert len(writer._h5["transport/rejected"]) == 1


def test_batch_packet_is_stored_once_with_hardlinks_and_remains_shared_after_resume(writer):
    packet = b"one exact compressed batch"
    base = metadata()
    base["source_envelope"]["frame_ids"] = [10, 11, 12, 13, 14, 15]
    for cycle in range(2):
        meta = json.loads(json.dumps(base))
        meta.update(packet_cycle_index=cycle, frame_indices=[10+3*cycle+i for i in range(3)])
        record(writer, frames(cycle+1), packet, meta=meta)
    writer.record_rejected_transport(packet, {"packet_cycle_index": 2}, "batch filter")
    assert len(writer._h5["transport/packets"]) == 1
    accepted = writer._h5["transport/accepted"]
    assert accepted["00000000/packet"].id == accepted["00000001/packet"].id
    assert accepted["00000000/packet"].id == writer._h5["transport/rejected/00000000/packet"].id
    writer.flush_transport()
    parent = writer.finalize("stopped")
    child = V0TangoRunWriter.resume_from(parent["h5_path"], config(), expected_plan=writer.plan)
    try:
        assert len(child._h5["transport/packets"]) == 1
        accepted = child._h5["transport/accepted"]
        assert accepted["00000000/packet"].id == accepted["00000001/packet"].id
        assert accepted["00000000/packet"].id == child._h5["transport/rejected/00000000/packet"].id
        assert accepted["00000000/packet"][...].tobytes() == packet
    finally:
        child.finalize("stopped")


def test_transport_flush_uses_os_fsync_and_propagates_durability_failure(writer, monkeypatch):
    import pump_probe_v0_storage as module
    record(writer, frames())
    called = []
    monkeypatch.setattr(module.os, "fsync", lambda handle: called.append(handle))
    writer.flush_transport()
    assert called == [writer._h5.id.get_vfd_handle()]
    def broken(_handle):
        raise OSError("disk durability failed")
    monkeypatch.setattr(module.os, "fsync", broken)
    with pytest.raises(OSError, match="disk durability failed"):
        writer.flush_transport()


def test_batch_cycle_mapping_must_match_original_envelope_before_commit(writer):
    meta = metadata(packet_cycle_index=1)
    with pytest.raises(ValueError, match="cycle index"):
        record(writer, frames(), meta=meta)
    assert writer.artifacts()["frame_counts"] == [0, 0, 0]


@pytest.mark.parametrize("change", [
    {"source_order_id": ""}, {"acquisition_epoch": None}, {"config_fingerprint": 5},
    {"frame_indices": [0, 2, 3]}, {"frame_indices": [True, 1, 2]}, {"frame_indices": [0, 1]},
    {"track_order": ["detector_II", "detector_I"]}, {"source_envelope": {}},
    {"phase_mapping": {"detector_I": {"BG": 0, "Ie": 1, "I0": 1},
                       "detector_II": {"BG": 0, "Ie": 1, "I0": 2}}},
])
def test_complete_cycle_requires_transport_identity_and_explicit_phase_classification(writer, change):
    with pytest.raises(ValueError):
        record(writer, frames(), meta=metadata(**change))
    assert writer.artifacts()["frame_counts"] == [0, 0, 0]
    assert len(writer._h5["transport/accepted"]) == 0
    assert len(writer._h5["transport/rejected"]) == 1


def test_resume_retains_packets_original_profile_and_partial_counts_without_replaying_padding(writer):
    record(writer, frames(1.), b"first")
    writer.record_rejected_transport(b"partial", metadata(), "stopped before six frames")
    parent = writer.finalize("stopped")
    parent_digest = hashlib.sha256(Path(parent["h5_path"]).read_bytes()).hexdigest()
    child = V0TangoRunWriter.resume_from(parent["h5_path"], config(), expected_plan=writer.plan,
                                         expected_wavelengths=[500., 600.])
    assert child.artifacts()["frame_counts"] == [1, 0, 0]
    assert child.artifacts()["parent_run_id"] == parent["run_id"]
    assert child._h5["transport/accepted/00000000/packet"][...].tobytes() == b"first"
    assert child._h5["transport/rejected/00000000/packet"][...].tobytes() == b"partial"
    record(child, frames(9.), b"second")
    child_result = child.finalize("stopped")
    assert child_result["frame_counts"] == [2, 0, 0]
    assert (child_result["next_point_index"], child_result["next_shot_index"]) == (1, 0)
    with h5py.File(child_result["h5_path"]) as handle:
        np.testing.assert_allclose(handle["od"][:, 0], np.log10(9) / 2)
        assert len(handle["transport/accepted"]) == 2
        assert np.isnan(handle["raw_data"][1:]).all()
    assert hashlib.sha256(Path(parent["h5_path"]).read_bytes()).hexdigest() == parent_digest


@pytest.mark.parametrize("tamper", ["profile", "packet", "slot", "layout", "missing"])
def test_resume_rejects_profile_calibration_or_transport_corruption_before_child_creation(writer, tamper, monkeypatch):
    record(writer, frames())
    parent = writer.finalize("stopped")
    changed = config()
    if tamper == "profile":
        changed["tango_profile"]["track_mapping"]["I"] = 1
    else:
        with h5py.File(parent["h5_path"], "a") as handle:
            if tamper == "packet":
                handle["transport/accepted/00000000/packet"][0] = 99
            elif tamper == "slot":
                item = handle["transport/accepted/00000000"]
                saved = envelope(item)
                saved["raw_slot"]["shot_index"] = 1
                item["envelope_json"][()] = json.dumps(saved)
            elif tamper == "layout":
                handle["metadata/raw_layout"][()] = TRANCON_LAYOUT
            else:
                del handle["transport/accepted/00000000"]
    monkeypatch.setattr(V0TangoRunWriter, "__init__", lambda *_a, **_kw: pytest.fail("Invalid resume created a child"))
    with pytest.raises(ValueError):
        V0TangoRunWriter.resume_from(parent["h5_path"], changed, expected_plan=writer.plan)


def test_u16_legacy_layout_still_rejects_fractional_or_large_counts():
    with pytest.raises(ValueError, match="integers in 0..65535"):
        calculate_raw_od([frames()[:, None, :]], TRANCON_LAYOUT)
    actual, _, _ = calculate_raw_od([frames()[:, None, :]], TRANCON_FLOAT_LAYOUT)
    np.testing.assert_allclose(actual, 0, atol=1e-15)


def test_tango_requires_profile_plan_and_explicit_transport_recording(writer):
    with pytest.raises(ValueError, match="tango_profile"):
        V0TangoRunWriter([500], writer.delays, writer.positions, 2, {}, plan=writer.plan)
    with pytest.raises(ValueError, match="immutable scan plan"):
        V0TangoRunWriter([500], writer.delays, writer.positions, 2, config())
    with pytest.raises(ValueError, match="record_tango_cycle"):
        writer.record_cycle(0, frames(), 0, 0)
    assert V0EmulatorRunWriter.raw_layout != V0TangoRunWriter.raw_layout
