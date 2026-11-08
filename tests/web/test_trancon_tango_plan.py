"""Frozen Tango intent and admission failures, without hardware or network."""

import copy
import hashlib
import json
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "web/backend"))

from pump_probe_v0_scanplan import ScanPlan
from pump_probe_v0_tango_plan import build_tango_plan, load_profile, validate_profile


PROFILE_PATH = ROOT / "web/pump_probe/config/v0_tango_raw_profile.json"


def profile():
    result = load_profile(PROFILE_PATH)
    result["commissioned"] = True
    result["expected_config_fingerprint"] = "c" * 64
    result["commissioning_status"] = "synthetic offline fixture; not a hardware commissioning claim"
    return result


def scan(delays=(0.0, 5.0, 0.0), shots=2):
    return ScanPlan(delays, tuple(-value * 0.1 for value in delays), shots,
                    0.0, 0.1, -10.0, 10.0)


def hardware():
    return {"control_mode": "tango", "owis_aggregator_device": "manip/general/OWIS",
            "andor_device": "manip/CR/ANDOR", "dg645_device": "manip/sync/DG645",
            "delay_line_axis": 3, "dg645_preflight_policy": "apply_recall_then_verify"}


def recall():
    return {"device": "manip/sync/DG645", "recall_slot": 8,
            "snapshot": {"raw_queries": {"*IDN?": "synthetic", "BURC?": "3", "TSRC?": "1"}},
            "restore": {"apply_commands": ["UNUSED SNAPSHOT COMMAND"]}}


def plan(**overrides):
    args = {"scan_plan": scan(), "hardware_config": hardware(), "profile": profile(),
            "dg645_recall": recall(), "output_context": {"output_dir": "C:/data/run", "sample_name": "sample"}}
    args.update(overrides)
    return build_tango_plan(**args)


def test_default_threshold_has_exact_legacy_origin_and_remains_uncommissioned():
    value = load_profile(PROFILE_PATH)
    assert value["background_level"] == 560000
    assert value["background_level_origin"]["source_sha256"] == "d260a09db330fad6696bc810246adbc0184ae63d59d417b889e81671782ca0cc"
    assert value["background_level_origin"]["automatic_calibration"] is False
    assert value["commissioned"] is False
    assert value["expected_config_fingerprint"] is None
    assert value["all_cycles"] is False
    assert value["order_timeout_s"] == 60
    with pytest.raises(ValueError, match="not commissioned"):
        load_profile(PROFILE_PATH, require_commissioned=True)
    # Pure plan preview remains available and discloses admission status.
    assert plan(profile=value).to_dict()["profile"]["commissioned"] is False


def test_plan_binds_order_repeats_batch_size_exact_commands_and_source_policies():
    value = plan()
    body = value.to_dict()
    assert body["scan_plan"]["delays_ps"] == [0.0, 5.0, 0.0]
    assert body["scan_plan"]["positions_mm"] == [-0.0, -0.5, -0.0]
    assert body["camera_batch_frames"] == 6
    assert body["phase_classifier_version"] == "trancon-clean-both-channels-sgl-v1"
    assert body["track_order"] == ["detector_I", "detector_II"]
    assert body["processing_mode"] == "fixed"
    assert body["invalid_triplet_policy"] == "reject_whole_physical_cycle"
    assert body["dg645"]["apply_commands"] == ["*RCL 8"]
    assert body["dg645"]["expected_raw_queries"] == [{"command": "BURC?", "expected": "3"}, {"command": "TSRC?", "expected": "1"}]
    assert body["dg645"]["restore_snapshot_commands_executed"] is False
    commands = [row["command"] for row in value.authorization_targets()]
    assert commands == ["state", "V0Capabilities", "start_grabbing", "V0BeginOrder", "V0OrderStatus", "V0ReadOrder",
                        "V0CancelOrder", "V0ReleaseOrder", "stop_grabbing", "move_axis",
                        "read_attribute:positions", "read_attribute:states", "stop_axis", "scpi_write", "scpi_query"]
    assert [row["command"] for row in body["cleanup"]] == ["V0CancelOrder", "V0ReadOrder", "V0ReleaseOrder", "stop_grabbing", "stop_axis"]
    assert body["cleanup"][-1] == {"device": hardware()["owis_aggregator_device"], "command": "stop_axis", "axis": 3, "when": "after run-owned motion"}
    assert body["camera_admission"]["parameter_mutations"] == []
    assert value.authorization_args() == body


def test_inputs_and_returned_nested_values_cannot_change_frozen_intent():
    p, h, d = profile(), hardware(), recall()
    value = plan(profile=p, hardware_config=h, dg645_recall=d)
    original = value.to_dict()
    p["background_level"] = 1
    h["delay_line_axis"] = 1
    d["snapshot"]["raw_queries"]["BURC?"] = "999"
    value.profile["filters"]["repump"]["enabled"] = True
    value.hardware_config["andor_device"] = "bad/input/device"
    value.dg645_recall["recall_slot"] = 1
    value.authorization_targets()[0]["device"] = "bad/input/device"
    value.authorization_args()["scan_plan"]["positions_mm"][1] = 9
    assert value.to_dict() == original
    assert value.scan_plan.delays == (0.0, 5.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        value._plan_json = "{}"


@pytest.mark.parametrize("change", ["position", "shots", "profile", "timeout", "device", "axis", "recall", "queries", "output", "action"])
def test_every_executable_choice_changes_approval_binding(change):
    original = plan()
    kwargs = {}
    if change == "position": kwargs["scan_plan"] = scan((0.0, 4.0, 0.0))
    if change == "shots": kwargs["scan_plan"] = scan(shots=3)
    if change in {"profile", "timeout"}:
        kwargs["profile"] = profile()
        kwargs["profile"]["background_level" if change == "profile" else "order_timeout_s"] = 99
    if change in {"device", "axis"}:
        kwargs["hardware_config"] = hardware()
        kwargs["hardware_config"]["andor_device" if change == "device" else "delay_line_axis"] = "manip/CR/OTHER" if change == "device" else 1
    if change in {"recall", "queries"}:
        kwargs["dg645_recall"] = recall()
        if change == "recall": kwargs["dg645_recall"]["recall_slot"] = 7
        else: kwargs["dg645_recall"]["snapshot"]["raw_queries"]["BURC?"] = "6"
    if change == "output": kwargs["output_context"] = {"output_dir": "C:/data/other", "sample_name": "other"}
    if change == "action": kwargs["run_action"] = "overwrite"
    changed = plan(**kwargs)
    assert original.fingerprint != changed.fingerprint
    assert original.authorization_args() != changed.authorization_args()


def test_canonical_json_and_profile_digests_are_reproducible():
    value = plan()
    reversed_hardware = dict(reversed(list(hardware().items())))
    assert plan(hardware_config=reversed_hardware).fingerprint == value.fingerprint
    body = value.to_dict()
    assert body["profile_sha256"] == hashlib.sha256(json.dumps(value.profile, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    assert body["dg645"]["source_sha256"] == hashlib.sha256(json.dumps(value.dg645_recall, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def test_continue_binds_exact_checkpoint_identity_hash_and_remaining_position():
    checkpoint = {"run_id": "parent-run", "source_sha256": "a" * 64,
                  "camera_config_fingerprint": "c" * 64,
                  "next_point_index": 1, "next_shot_index": 1, "frame_counts": [2, 1, 0]}
    value = plan(run_action="continue", checkpoint=checkpoint)
    assert value.to_dict()["checkpoint"] == checkpoint
    changed = copy.deepcopy(checkpoint)
    changed["source_sha256"] = "b" * 64
    assert plan(run_action="continue", checkpoint=changed).fingerprint != value.fingerprint
    checkpoint["frame_counts"][0] = 0
    assert value.to_dict()["checkpoint"]["frame_counts"] == [2, 1, 0]


@pytest.mark.parametrize("field,value", [("background_level", None), ("background_level", True), ("background_level", 1.5),
                                         ("background_level", 2**31), ("order_timeout_s", 0), ("move_timeout_s", float("inf")),
                                         ("poll_interval_s", 0.001), ("max_rejected_cycles", -1), ("max_rejected_cycles", True),
                                         ("all_cycles", 1), ("frames_per_cycle", 4), ("tracks", ["detector_II", "detector_I"]),
                                         ("classifier_version", "unknown"), ("processing_mode", "fixed-auto")])
def test_invalid_profile_fails_purely(field, value):
    candidate = profile()
    candidate[field] = value
    with pytest.raises(ValueError): plan(profile=candidate)


def test_all_false_default_and_all_true_quirk_are_explicit_and_fingerprinted():
    p = profile()
    del p["all_cycles"]
    assert plan(profile=p).profile["all_cycles"] is False
    p["all_cycles"] = True
    assert plan(profile=p).to_dict()["invalid_triplet_policy"] == "source_All_true_fallback_quirk"
    assert plan(profile=p).fingerprint != plan().fingerprint


@pytest.mark.parametrize("key,value", [("andor_device", "manip/*/ANDOR"), ("andor_device", " manip/CR/ANDOR"),
                                       ("dg645_device", "other/sync/DG645"), ("delay_line_axis", True),
                                       ("delay_line_axis", 0), ("dg645_preflight_policy", "off")])
def test_invalid_physical_config_fails_before_any_transport(key, value):
    candidate = hardware()
    candidate[key] = value
    with pytest.raises(ValueError): plan(hardware_config=candidate)


def test_dg645_verification_only_excludes_write_capability_and_empty_queries_fail():
    h = hardware()
    h["dg645_preflight_policy"] = "verify_only"
    value = plan(hardware_config=h)
    assert value.to_dict()["dg645"]["apply_commands"] == []
    assert {"device": h["dg645_device"], "command": "scpi_write"} not in value.authorization_targets()
    for queries in ({}, {"BURC?;*RST": "3"}, {"*RST": "3"}):
        d = recall()
        d["snapshot"]["raw_queries"] = queries
        with pytest.raises(ValueError): plan(dg645_recall=d)


def test_commissioned_repump_and_unsupported_ml_fail_before_runtime():
    p = profile()
    p["filters"]["repump"] = {"enabled": True, "version": "external-aligned-values-v1", "repump_min": 1, "repump_max": 2}
    with pytest.raises(ValueError, match="external aligned monitor"): plan(profile=p)
    p["commissioned"] = False
    assert plan(profile=p).profile["filters"]["repump"]["enabled"] is True
    with pytest.raises(ValueError): validate_profile(p, require_commissioned=True)
    p = profile()
    p["filters"]["similarity"] = {"enabled": True, "threshold_ref_channel": 1,
                                    "version": "trancon-python-batch-distance-v1", "mode": "ml"}
    with pytest.raises(ValueError, match="External ML"): plan(profile=p)


def test_lossless_camera_admission_types_and_parameters_are_frozen():
    for key, value in (("external_trigger", False), ("parameter_writes", True), ("track_count", 3)):
        p = profile()
        p["camera_admission"][key] = value
        with pytest.raises(ValueError): plan(profile=p)
    p = profile()
    p["camera_admission"]["external_trigger"] = 1
    with pytest.raises(ValueError): plan(profile=p)


def test_missing_or_unbounded_checkpoint_and_bad_output_fail():
    with pytest.raises(ValueError): plan(run_action="continue")
    with pytest.raises(ValueError): plan(checkpoint={})
    checkpoint = {"run_id": "parent", "source_sha256": "a" * 64,
                  "camera_config_fingerprint": "c" * 64, "next_point_index": 3, "next_shot_index": 0}
    with pytest.raises(ValueError, match="next_point_index"): plan(run_action="continue", checkpoint=checkpoint)
    with pytest.raises(ValueError): plan(output_context={"output_dir": "", "sample_name": "sample"})


@pytest.mark.parametrize("counts,next_point,next_shot", [([2, 1], 1, 1), ([2, 1, 1], 1, 1),
                                                         ([2, 1, 0], 1, 0), ([2, 2, 2], 2, 0),
                                                         ([True, 1, 0], 1, 1)])
def test_resume_counts_cannot_rebind_duplicate_delay_rows(counts, next_point, next_shot):
    checkpoint = {"run_id": "parent", "source_sha256": "a" * 64,
                  "camera_config_fingerprint": "c" * 64,
                  "frame_counts": counts, "next_point_index": next_point, "next_shot_index": next_shot}
    with pytest.raises(ValueError): plan(run_action="continue", checkpoint=checkpoint)


def test_maximum_supported_camera_batch_is_600_frames():
    assert plan(scan_plan=scan(shots=200)).to_dict()["camera_batch_frames"] == 600
    with pytest.raises(ValueError): scan(shots=201)


def test_profile_json_duplicate_keys_and_overflow_rejected(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text('{"schema":"v0-tango-raw-profile-v1","schema":"bad"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"): load_profile(p)
    candidate = profile()
    candidate["order_timeout_s"] = 1e308
    p.write_text(json.dumps(candidate).replace("1e+308", "1e999"), encoding="utf-8")
    with pytest.raises(ValueError, match="finite JSON"): load_profile(p)


@pytest.mark.parametrize("fingerprint", [None, "", "c" * 63, "x" * 64, 1, True])
def test_commissioning_requires_actual_readout_fingerprint(fingerprint):
    p = profile()
    p["expected_config_fingerprint"] = fingerprint
    with pytest.raises(ValueError, match="fingerprint"): plan(profile=p)


def test_continue_requires_same_commissioned_camera_configuration():
    checkpoint = {"run_id": "parent", "source_sha256": "a" * 64,
                  "next_point_index": 0, "next_shot_index": 0}
    with pytest.raises(ValueError, match="camera_config_fingerprint"):
        plan(run_action="continue", checkpoint=checkpoint)
    checkpoint["camera_config_fingerprint"] = "d" * 64
    with pytest.raises(ValueError, match="does not match"):
        plan(run_action="continue", checkpoint=checkpoint)
    checkpoint["camera_config_fingerprint"] = "c" * 64
    value = plan(run_action="continue", checkpoint=checkpoint)
    assert value.to_dict()["checkpoint"] == checkpoint
    assert value.to_dict()["camera_admission"]["expected_config_fingerprint"] == "c" * 64
    p = profile()
    p["expected_config_fingerprint"] = "d" * 64
    assert plan(profile=p).fingerprint != plan().fingerprint
