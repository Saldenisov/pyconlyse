"""Offline qualification evidence: original device packets, no camera SDK."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import h5py
import numpy as np
import pytest
from flask import Flask, jsonify

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "web/backend"))
from DeviceServers.cameras.andor.v0_orders import V0Orders, config_fingerprint
from pump_probe_v0_commissioning import (
    SCHEMA, SNAPSHOT_SCHEMA, _i32_interval, analyze_manifest, check_snapshot, write_bundle,
)
from pump_probe_v0_config import DEFAULT_HARDWARE_CONFIG
from pump_probe_v0_scanplan import build_scan_plan
from pump_probe_v0_storage import V0TangoRunWriter
from pump_probe_v0_tango import decode_tango_batch
from pump_probe_v0_tango_plan import validate_profile
from tools.analysis.commission_v0_andor import main, prepare

NOW = datetime.now(timezone.utc)
DEVICE = DEFAULT_HARDWARE_CONFIG["andor_device"]


def dump(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
    return path


def make_packet(path, *, dtype="<u2", count=30, config_changes=None, data_change=None):
    config = {"trigger_mode": "ext", "read_mode": "multi_track", "acquisition_mode": "cont",
              "track_count": 2, "width": 4, "wavelengths": [500.0000000001, 600., 500.0000000002, 700.],
              "exposure_seconds": .001, "multi_track": [2, 1, 0], "amplifier": [0, 0, 0, 0],
              "axis_source": "configured_calibration", "indexed_buffer_size": 1000,
              "emccd_gain": {"method_present": True, "value": None},
              **(config_changes or {})}
    book = V0Orders()
    book.new_epoch()
    caps = book.observe(config, True)
    order = book.begin({"request_id": "test-order", "run_id": "real-format-synthetic-test", "point_index": 0,
                       "frame_count": count * 3, "acquisition_epoch": caps["acquisition_epoch"],
                       "expected_config_fingerprint": caps["config_fingerprint"]})
    data = np.empty((count * 3, 2, 4), dtype=dtype)
    for index in range(count):
        data[3*index] = 10
        data[3*index+1] = 2
        data[3*index+2] = 20
    if data_change:
        data_change(data)

    class SDK:
        frames = []
        cursor = 0

        def get_frames_status(self):
            return SimpleNamespace(acquired=len(self.frames), buffer_size=1000)

        def get_new_images_range(self):
            return (self.cursor, len(self.frames)) if self.cursor < len(self.frames) else None

        def read_multiple_images(self, *, rng, **kwargs):
            self.cursor = rng[1]
            return self.frames[rng[0]:rng[1]], rng

    sdk = SDK()
    book.pump(sdk)
    sdk.frames = list(data)
    book.pump(sdk)
    header, packet = book.read(order["order_id"])
    header_path = path / (order["order_id"] + ".header.json")
    payload_path = path / (order["order_id"] + ".payload.bin")
    header_path.write_bytes(header.encode("utf-8"))
    payload_path.write_bytes(packet)
    return caps, header_path, payload_path


@pytest.fixture
def evidence(tmp_path):
    caps, header_path, payload_path = make_packet(tmp_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_bytes((ROOT / "web/pump_probe/config/v0_tango_raw_profile.json").read_bytes())
    snapshot_path = dump(tmp_path / "capabilities.json", {"schema": SNAPSHOT_SCHEMA, "device": DEVICE,
                         "captured_at_utc": NOW.isoformat(), "capabilities": caps})
    header = json.loads(header_path.read_text())
    manifest = {"schema": SCHEMA, "profile_path": str(profile_path), "capabilities_path": str(snapshot_path),
                "andor_device": DEVICE, "minimum_cycles": 30, "max_snapshot_age_seconds": 900,
                "sources": [{"kind": "packet", "header_path": str(header_path), "payload_path": str(payload_path)}],
                "bg_labels": [{"order_id": header["order_id"], "frame_ids": header["frame_ids"][1::3],
                               "basis": "independent_optical_control", "evidence": "Synthetic fixture only: controlled dark slot"}]}
    manifest_path = dump(tmp_path / "manifest.json", manifest)
    return SimpleNamespace(tmp=tmp_path, caps=caps, header_path=header_path, payload_path=payload_path,
                           profile_path=profile_path, snapshot_path=snapshot_path, manifest=manifest, path=manifest_path)


def analyze(evidence, **kwargs):
    dump(evidence.path, evidence.manifest)
    return analyze_manifest(evidence.path, now=kwargs.pop("now", NOW), **kwargs)


def test_actual_protocol_replay_finds_guarded_threshold_and_preserves_every_original_byte(evidence):
    originals = {p: p.read_bytes() for p in (evidence.header_path, evidence.payload_path, evidence.profile_path, evidence.snapshot_path)}
    report, candidate, packets = analyze(evidence)
    assert report["status"] == "ready_for_operator_review" and report["issues"] == []
    assert report["cycle_count"] == report["independently_labeled_cycles"] == 30
    assert report["observed_I32_interval_inclusive"] == [9, 40]
    assert report["guarded_I32_interval_inclusive"] == [9, 39]
    assert report["candidate_replay"]["matched_cycles"] == 30
    assert report["current_profile_replay"]["multiple_BG"] == 30
    assert candidate["expected_config_fingerprint"] == evidence.caps["config_fingerprint"]
    assert candidate["expected_sample_dtype"] == "<u2"
    assert candidate["background_level"] == 24 and candidate["commissioned"] is False
    saved = write_bundle(evidence.tmp / "output", report, candidate, packets)
    assert all(p.read_bytes() == data for p, data in originals.items())
    with h5py.File(evidence.tmp / "output/original_raw_packets.h5", "r") as handle:
        assert handle["packets/0000/header_utf8"][...].tobytes() == originals[evidence.header_path]
        assert handle["packets/0000/payload"][...].tobytes() == originals[evidence.payload_path]
    assert saved["commissioned"] is False
    output_candidate = json.loads((evidence.tmp / "output/profile.candidate.json").read_text())
    assert output_candidate["commissioned"] is False
    report_bytes = (evidence.tmp / "output/report.json").read_bytes()
    assert output_candidate["background_level_origin"]["report_sha256"] == hashlib.sha256(report_bytes).hexdigest()
    with pytest.raises(FileExistsError):
        write_bundle(evidence.tmp / "output", report, candidate, packets)


def test_darkest_triplet_is_only_a_hypothesis_and_never_commissions(evidence):
    evidence.manifest["bg_labels"] = []
    report, candidate, _ = analyze(evidence)
    assert report["status"] == "pending_or_blocked"
    assert report["issues"] == ["independent_BG_control_required"]
    assert all(r["basis"] == "darkest_triplet_hypothesis" for r in report["cycles"])
    assert candidate is not None and candidate["commissioned"] is False


@pytest.mark.parametrize("age", [901, -6])
def test_stale_or_future_snapshot_blocks_candidate_profile(evidence, age):
    report, candidate, _ = analyze(evidence, now=NOW + timedelta(seconds=age))
    assert "capability_snapshot_stale_or_future" in report["issues"]
    assert candidate is None


@pytest.mark.parametrize("mutation", ["fingerprint", "device", "axis", "configuration_fresh"])
def test_invalid_snapshot_never_qualifies(evidence, mutation):
    snapshot = json.loads(evidence.snapshot_path.read_text())
    if mutation == "fingerprint":
        snapshot["capabilities"]["config_fingerprint"] = "0" * 64
    elif mutation == "device":
        snapshot["device"] = "another/camera/1"
    elif mutation == "axis":
        snapshot["capabilities"]["wavelengths"][0] += .001
    else:
        snapshot["capabilities"]["configuration_fresh"] = False
    dump(evidence.snapshot_path, snapshot)
    with pytest.raises(ValueError):
        analyze(evidence)


def test_buffer_allocation_is_not_a_sampling_change_but_exposure_is(evidence):
    snapshot = json.loads(evidence.snapshot_path.read_text())
    snapshot["capabilities"]["configuration"]["indexed_buffer_size"] = 2000
    dump(evidence.snapshot_path, snapshot)
    assert analyze(evidence)[0]["status"] == "ready_for_operator_review"
    snapshot["capabilities"]["configuration"]["exposure_seconds"] = .5
    snapshot["capabilities"]["config_fingerprint"] = config_fingerprint(snapshot["capabilities"]["configuration"])
    dump(evidence.snapshot_path, snapshot)
    report, candidate, _ = analyze(evidence)
    assert "RAW_configuration_differs_from_snapshot" in report["issues"]
    assert candidate is None


def test_stopped_camera_can_qualify_sampling_but_is_not_runtime_admitted(evidence):
    snapshot = json.loads(evidence.snapshot_path.read_text())
    snapshot["capabilities"].update(lossless=False, acquisition_active=False, admission_error="inactive")
    snapshot["capabilities"]["configuration"]["indexed_buffer_size"] = 0
    dump(evidence.snapshot_path, snapshot)
    report, candidate, _ = analyze(evidence)
    assert report["status"] == "ready_for_operator_review"
    assert report["snapshot"]["runtime_admitted"] is False
    assert candidate["commissioned"] is False


def test_wrong_independent_BG_label_exposes_overlap_instead_of_using_argmin(evidence):
    evidence.manifest["bg_labels"][0]["frame_ids"] = list(range(0, 90, 3))
    report, candidate, _ = analyze(evidence)
    assert "no_global_I32_threshold_separates_observed_BG_and_light" in report["issues"]
    assert candidate is None


@pytest.mark.parametrize("case", ["drift", "rounding"])
def test_clean_local_triplets_do_not_qualify_without_a_global_guarded_threshold(evidence, case):
    def change(data):
        if case == "drift":
            for i in range(15, 30):
                data[3*i, 1] = 20
                data[3*i+1, 1] = 12
                data[3*i+2, 1] = 30
        else:
            # Adversarial arithmetic fixture, not an optical measurement:
            # sequential SGL sums 2,0,4; another reduction tree can differ.
            data[:, 1] = [1.e8, 1., -1.e8, 0.]
            data[0::3, 1, 3] = 2.
            data[2::3, 1, 3] = 4.
    caps, hp, pp = make_packet(evidence.tmp, dtype="<f4", data_change=change)
    header = json.loads(hp.read_text())
    evidence.manifest["sources"] = [{"kind": "packet", "header_path": str(hp), "payload_path": str(pp)}]
    evidence.manifest["bg_labels"][0]["order_id"] = header["order_id"]
    report, candidate, _ = analyze(evidence)
    assert report["independently_labeled_cycles"] == 30
    assert candidate is None and report["guarded_I32_interval_inclusive"] is None
    if case == "drift":
        assert "no_global_I32_threshold_separates_observed_BG_and_light" in report["issues"]
    else:
        assert report["observed_I32_interval_inclusive"] == [1, 2]
        assert "no_threshold_with_SGL_reduction_rounding_guard" in report["issues"]


def test_unmatched_or_multiple_BG_labels_are_not_silently_ignored(evidence):
    evidence.manifest["bg_labels"][0]["frame_ids"].append(900)
    report, candidate, _ = analyze(evidence)
    assert "BG_annotations_not_matched_to_qualifying_cycles" in report["issues"] and candidate is None
    evidence.manifest["bg_labels"][0]["frame_ids"] = [0, 1]
    report, candidate, _ = analyze(evidence)
    assert any("Multiple independently" in issue for issue in report["issues"])


@pytest.mark.parametrize("bg,light,expected", [
    (8., 40., [9, 40]), (2.**24, 2.**24+2, [16777218, 16777218]),
    (1., 1., None), (2.**31, 2.**32, None), (-2., 0., [-1, 0]),
])
def test_I32_interval_obeys_strict_SGL_comparison_and_rounding_plateaus(bg, light, expected):
    assert _i32_interval(bg, light) == expected


def test_repeated_packet_cannot_pad_cycle_coverage(evidence):
    evidence.manifest["sources"] *= 2
    evidence.manifest["minimum_cycles"] = 31
    report, candidate, _ = analyze(evidence)
    assert report["cycle_count"] == 30 and report["unique_original_packets"] == 1
    assert "insufficient_cycle_coverage" in report["issues"]
    assert candidate["commissioned"] is False


def test_corrupt_original_payload_is_archived_and_cannot_produce_candidate(evidence):
    evidence.payload_path.write_bytes(b"not a zlib payload")
    report, candidate, packets = analyze(evidence)
    assert candidate is None and any(i.startswith("invalid_packet:") for i in report["issues"])
    write_bundle(evidence.tmp / "corrupt-report", report, candidate, packets)
    with h5py.File(evidence.tmp / "corrupt-report/original_raw_packets.h5", "r") as handle:
        assert handle["packets/0000/payload"][...].tobytes() == b"not a zlib payload"


@pytest.mark.parametrize("category", ["accepted", "rejected"])
def test_HDF5_reads_original_packets_once_and_ignores_previous_classifier_selection(evidence, category):
    profile = json.loads(evidence.profile_path.read_text())
    plan = build_scan_plan({"delay_points_ps": [0., 1.], "pulses_per_point": 30,
                            "real_zero_ps": 0., "calibration_version": "synthetic"}, .5, -2., 2.)
    writer = V0TangoRunWriter([500.0000000001, 600., 500.0000000002, 700.], plan.delays, plan.positions, 30,
                             {"tango_profile": profile}, plan=plan)
    header_text = evidence.header_path.read_text()
    packet = evidence.payload_path.read_bytes()
    header = json.loads(header_text)
    if category == "rejected":
        writer.record_rejected_transport(packet, {"raw_header": header_text}, "Old threshold rejected these original samples")
    else:
        batch = decode_tango_batch((header_text, packet), order_id=header["order_id"], run_id=header["run_id"],
            point_index=0, acquisition_epoch=header["acquisition_epoch"], config_fingerprint=header["config_fingerprint"],
            wavelengths=header["wavelengths"], background_level=24, cycle_count=30)
        for cycle in batch.cycles:
            writer.record_tango_cycle(0, cycle.frames, plan.positions[0], plan.positions[0], packet, cycle.metadata)
    saved = writer.finalize("stopped")
    path = Path(saved["h5_path"])
    before = path.read_bytes()
    evidence.manifest["sources"] = [{"kind": "v0_h5", "path": str(path)}]
    report, candidate, packets = analyze(evidence)
    assert report["status"] == "ready_for_operator_review" and len(packets) == 1
    assert report["cycle_count"] == 30 and candidate["commissioned"] is False
    assert path.read_bytes() == before
    evidence.manifest["sources"][0]["order_ids"] = ["missing-order"]
    with pytest.raises(ValueError, match="not found"):
        analyze(evidence)


def test_canonical_RAW_only_is_insufficient_for_commissioning(evidence):
    path = evidence.tmp / "canonical.h5"
    with h5py.File(path, "w") as handle:
        handle.create_dataset("raw_data", data=np.zeros((2, 6, 30, 4)))
    evidence.manifest["sources"] = [{"kind": "v0_h5", "path": str(path)}]
    with pytest.raises(ValueError, match="canonical RAW alone"):
        analyze(evidence)


def test_network_paths_and_duplicate_JSON_keys_are_rejected_without_device_access(evidence):
    evidence.manifest["sources"][0]["payload_path"] = "smb://not-accessed/share/file.bin"
    with pytest.raises(ValueError, match="local file path"):
        analyze(evidence)
    evidence.path.write_text('{"schema":"x","schema":"y"}')
    with pytest.raises(ValueError, match="Duplicate JSON"):
        analyze_manifest(evidence.path)


def test_prepare_creates_only_local_pending_inputs_and_never_overwrites(evidence):
    original = evidence.profile_path.read_bytes()
    output = evidence.tmp / "prepared"
    result = prepare(output, evidence.profile_path)
    manifest = json.loads((output / "manifest.json").read_text())
    assert result["hardware_access"] is False and result["commissioned"] is False
    assert manifest["sources"] == [] and manifest["bg_labels"] == []
    assert not (output / "capabilities.snapshot.json").exists()
    assert evidence.profile_path.read_bytes() == original
    with pytest.raises(FileExistsError):
        prepare(output, evidence.profile_path)


def test_CLI_produces_new_bundle_without_activating_profile(evidence, capsys):
    output = evidence.tmp / "cli-check"
    before = evidence.profile_path.read_bytes()
    assert main(["analyze", "--manifest", str(evidence.path), "--output", str(output)]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["commissioned"] is False and response["hardware_access"] is False
    assert evidence.profile_path.read_bytes() == before
    assert json.loads((output / "profile.candidate.json").read_text())["commissioned"] is False


def test_output_rejects_activated_profile_even_if_called_directly(evidence):
    report, candidate, packets = analyze(evidence)
    candidate["commissioned"] = True
    with pytest.raises(ValueError, match="must not activate"):
        write_bundle(evidence.tmp / "bad-output", report, candidate, packets)
    assert not (evidence.tmp / "bad-output").exists()


@pytest.mark.parametrize("dtype", ["float32", ">i4", "<f8", True, 2, [], {}])
def test_profile_rejects_unqualified_expected_SDK_dtype(evidence, dtype):
    profile = json.loads(evidence.profile_path.read_text())
    profile["expected_sample_dtype"] = dtype
    with pytest.raises(ValueError, match="expected_sample_dtype"):
        validate_profile(profile)


@pytest.fixture
def snapshot_route(evidence, monkeypatch):
    import pump_probe_v0_api as api
    controller = api.PumpProbeV0Controller()
    controller._hardware_config["control_mode"] = "tango"
    monkeypatch.setattr(api, "_emulator", controller)
    events = []

    def guard(action, targets, args, **kwargs):
        events.append("guard")
        assert action == kwargs["route_id"] == "v0.andor-snapshot"
        assert targets == [{"device": DEVICE, "command": "V0Capabilities"}]
        assert args == {"andor_device": DEVICE, "readback": "V0Capabilities", "purpose": "BG_level_and_sampling_fingerprint"}
        assert kwargs["wrapper_fields"] == set()

    class Proxy:
        def command_inout(self, name):
            assert name == "V0Capabilities"
            events.append(name)
            return json.dumps(evidence.caps)

    def factory(device, **kwargs):
        assert device == DEVICE and kwargs == {"timeout_ms": 2500}
        events.append("proxy")
        return Proxy()

    monkeypatch.setattr(api, "_tango_proxy", factory)
    monkeypatch.setattr(api, "require_http_hardware", guard)
    app = Flask(__name__)
    app.register_blueprint(api.pump_probe_v0_api)
    return SimpleNamespace(api=api, controller=controller, events=events, client=app.test_client())


def test_snapshot_endpoint_only_reads_one_capability_after_exact_authorization(snapshot_route):
    result = snapshot_route.client.post("/api/pump-probe-v0/commissioning/andor-snapshot", json={})
    assert result.status_code == 200, result.get_json()
    snapshot = result.get_json()["snapshot"]
    checked = check_snapshot(snapshot, DEVICE, now=datetime.now(timezone.utc))
    assert checked["config_fingerprint"] == snapshot["capabilities"]["config_fingerprint"]
    assert snapshot_route.events == ["guard", "proxy", "V0Capabilities"]
    assert snapshot_route.controller._run_writer is None


def test_snapshot_denied_authorization_has_no_proxy_or_camera_calls(snapshot_route, monkeypatch):
    monkeypatch.setattr(snapshot_route.api, "require_http_hardware", lambda *a, **k: (jsonify({"success": False}), 428))
    result = snapshot_route.client.post("/api/pump-probe-v0/commissioning/andor-snapshot", json={})
    assert result.status_code == 428 and snapshot_route.events == []


@pytest.mark.parametrize("active", ["running", "realtime", "order_cleanup", "done_pending"])
def test_snapshot_waits_for_acquisition_and_cleanup_without_device_access(snapshot_route, active):
    controller = snapshot_route.controller
    if active == "running":
        controller._running = True
    elif active == "realtime":
        controller._real_time = True
    elif active == "order_cleanup":
        controller._tango_stop_event = threading.Event()
    else:
        controller._tango_done_event.clear()
    result = snapshot_route.client.post("/api/pump-probe-v0/commissioning/andor-snapshot", json={})
    assert result.status_code == 409 and snapshot_route.events == []


@pytest.mark.parametrize("raw", ['{"device":"another/camera/1"}', 'null', '[]', '{invalid'])
def test_snapshot_rejects_payload_overrides_or_malformed_JSON_without_hardware(snapshot_route, raw):
    response = snapshot_route.client.post("/api/pump-probe-v0/commissioning/andor-snapshot", data=raw, content_type="application/json")
    assert response.status_code == 400 and snapshot_route.events == []
