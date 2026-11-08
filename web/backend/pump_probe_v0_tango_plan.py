"""Pure immutable V0 Tango intent; no device discovery or hardware calls."""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from pump_probe_v0_detector_filters import validate_detector_filter_settings
from pump_probe_v0_scanplan import ScanPlan


PROFILE_SCHEMA = "v0-tango-raw-profile-v1"
PLAN_SCHEMA = "v0-tango-run-plan-v1"
CLASSIFIER_VERSION = "trancon-clean-both-channels-sgl-v1"
TRACKS = ["detector_I", "detector_II"]
PACKET_SCHEMA = "andor-v0-raw-order-v1"
_DEVICE = re.compile(r"[A-Za-z0-9_.:-]+/[A-Za-z0-9_.:-]+/[A-Za-z0-9_.:-]+\Z")
_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan values must be finite JSON") from exc


def _copy(value):
    return json.loads(_canonical(value))


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer in {lower}..{upper}")
    return value


def _positive(value, name, lower=0.0):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= lower:
        raise ValueError(f"{name} must be finite and greater than {lower}")
    return float(value)


def _device(value, name):
    if not isinstance(value, str) or not _DEVICE.fullmatch(value):
        raise ValueError(f"{name} must be an exact non-wildcard Tango device")
    return value


def validate_profile(profile, *, require_commissioned=False):
    """Validate explicit detector choices; commissioning is an external fact."""
    if not isinstance(profile, dict) or profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"Detector profile schema must be {PROFILE_SCHEMA}")
    result = _copy(profile)
    allowed = {"schema", "profile_version", "source_references", "background_level_origin",
               "background_level", "commissioned", "commissioning_status", "all_cycles",
               "frames_per_cycle", "tracks", "classifier_version", "move_tolerance_mm",
               "settled_samples", "move_timeout_s", "order_timeout_s", "poll_interval_s",
               "max_rejected_cycles", "camera_admission", "filters", "processing_mode",
               "expected_config_fingerprint", "expected_sample_dtype"}
    if set(result) - allowed:
        raise ValueError("Unknown detector profile field")
    if not isinstance(result.get("profile_version"), str) or not result["profile_version"].strip():
        raise ValueError("profile_version must be explicit")
    result["background_level"] = _integer(result.get("background_level"), "background_level", -(2**31), 2**31 - 1)
    result.setdefault("processing_mode", "fixed")
    if result["processing_mode"] != "fixed":
        raise ValueError("Only fixed processing_mode is supported; fixed-auto is not qualified")
    result.setdefault("all_cycles", False)
    if type(result["all_cycles"]) is not bool or type(result.get("commissioned")) is not bool:
        raise ValueError("all_cycles and commissioned must be booleans")
    result.setdefault("expected_config_fingerprint", None)
    result.setdefault("expected_sample_dtype", None)
    if result["expected_sample_dtype"] is not None and result["expected_sample_dtype"] not in ("<u2", "<i4", "<f4"):
        raise ValueError("expected_sample_dtype must be <u2, <i4, <f4, or null")
    expected_config = result["expected_config_fingerprint"]
    if expected_config is not None:
        if not isinstance(expected_config, str) or not _SHA.fullmatch(expected_config):
            raise ValueError("expected_config_fingerprint must be a 64-hex SHA256")
        result["expected_config_fingerprint"] = expected_config.lower()
    if result["commissioned"] and expected_config is None:
        raise ValueError("Commissioned profile requires expected_config_fingerprint for the actual camera readout")
    if require_commissioned and not result["commissioned"]:
        raise ValueError("V0 Tango profile is not commissioned for the current Andor configuration")
    if type(result.get("frames_per_cycle")) is not int or result["frames_per_cycle"] != 3:
        raise ValueError("frames_per_cycle must be 3")
    if result.get("tracks") != TRACKS or result.get("classifier_version") != CLASSIFIER_VERSION:
        raise ValueError("Detector tracks/classifier version do not match the V0 source contract")
    for key in ("move_tolerance_mm", "move_timeout_s", "order_timeout_s"):
        result[key] = _positive(result.get(key), key)
    result["poll_interval_s"] = _positive(result.get("poll_interval_s"), "poll_interval_s", 0.001)
    result["settled_samples"] = _integer(result.get("settled_samples"), "settled_samples", 1, 1000)
    result["max_rejected_cycles"] = _integer(result.get("max_rejected_cycles"), "max_rejected_cycles", 0, 10000)
    admission = result.get("camera_admission")
    if (not isinstance(admission, dict)
            or admission != {"external_trigger": True, "track_count": 2, "parameter_writes": False,
                             "packet_schema": PACKET_SCHEMA}):
        raise ValueError("Camera admission requires external trigger, two tracks and no parameter writes")
    # bool compares equal to integer 1/0; require the admission ABI types too.
    if type(admission["track_count"]) is not int or type(admission["external_trigger"]) is not bool or type(admission["parameter_writes"]) is not bool:
        raise ValueError("Camera admission types are invalid")
    filters = validate_detector_filter_settings(result)
    result["filters"] = {key: value for key, value in filters.items() if key != "all_cycles"}
    if (require_commissioned or result["commissioned"]) and filters["repump"]["enabled"]:
        raise ValueError("Enabled repump requires an external aligned monitor; Tango camera profile cannot supply it")
    return result


def load_profile(path, require_commissioned=False):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate profile key: {key}")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("Profile JSON must be finite")

    with Path(path).open("r", encoding="utf-8") as handle:
        profile = json.load(handle, object_pairs_hook=pairs, parse_constant=reject_constant)
    return validate_profile(profile, require_commissioned=require_commissioned)


@dataclass(frozen=True)
class TangoRunPlan:
    scan_plan: ScanPlan
    _profile_json: str
    _hardware_json: str
    _dg645_json: str
    _plan_json: str

    @property
    def profile(self):
        return json.loads(self._profile_json)

    @property
    def hardware_config(self):
        return json.loads(self._hardware_json)

    @property
    def dg645_recall(self):
        return json.loads(self._dg645_json)

    @property
    def fingerprint(self):
        return hashlib.sha256(self._plan_json.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {**json.loads(self._plan_json), "fingerprint": self.fingerprint}

    def authorization_args(self):
        return self.to_dict()

    def authorization_targets(self):
        return json.loads(self._plan_json)["targets"]


def build_tango_plan(scan_plan, hardware_config, profile, dg645_recall,
                     run_action="new", checkpoint=None, *, output_context=None):
    """Freeze exact intent before authorization, proxy construction or workers.

    Preview permits an uncommissioned profile. The execution entry point must
    load/validate with require_commissioned=True before consuming approval.
    No camera-generated order, epoch or configuration identifiers are invented.
    """
    if not isinstance(scan_plan, ScanPlan):
        raise ValueError("scan_plan must be a validated ScanPlan")
    _integer(scan_plan.shots_per_point, "shots_per_point", 1, 200)
    if run_action not in {"new", "overwrite", "continue"}:
        raise ValueError("A Tango plan requires new, overwrite or continue")
    p = validate_profile(profile)
    if not isinstance(hardware_config, dict) or not isinstance(dg645_recall, dict):
        raise ValueError("Hardware configuration and DG645 recall must be objects")
    hardware = _copy(hardware_config)
    dg645 = _copy(dg645_recall)
    for key in ("owis_aggregator_device", "andor_device", "dg645_device"):
        _device(hardware.get(key), key)
    axis = _integer(hardware.get("delay_line_axis"), "delay_line_axis", 1, 64)
    if "control_mode" in hardware and hardware["control_mode"] != "tango":
        raise ValueError("Tango run hardware control_mode must be tango")
    if dg645.get("device") != hardware["dg645_device"]:
        raise ValueError("DG645 recall device does not match the exact configured target")
    slot = _integer(dg645.get("recall_slot"), "DG645 recall_slot", 0, 9)
    policy = hardware.get("dg645_preflight_policy", "apply_recall_then_verify")
    if policy not in {"apply_recall_then_verify", "verify_only"}:
        raise ValueError("Tango scan requires explicit DG645 recall/verification policy")
    snapshot = dg645.get("snapshot")
    queries = snapshot.get("raw_queries") if isinstance(snapshot, dict) else None
    if not isinstance(queries, dict) or not queries:
        raise ValueError("DG645 recall requires nonempty expected raw_queries")
    for command, expected in queries.items():
        if (not isinstance(command, str) or "?" not in command or not command.isascii()
                or any(char in command for char in "\r\n;")
                or not isinstance(expected, (str, int, float)) or isinstance(expected, bool)):
            raise ValueError("DG645 expected query/response is invalid")
    saved = _copy(checkpoint) if checkpoint is not None else None
    if run_action == "continue":
        if (not isinstance(saved, dict) or not isinstance(saved.get("run_id"), str)
                or not saved["run_id"] or not isinstance(saved.get("source_sha256"), str)
                or not _SHA.fullmatch(saved["source_sha256"])):
            raise ValueError("Continue requires checkpoint run_id and exact source_sha256")
        camera_config = saved.get("camera_config_fingerprint")
        if not isinstance(camera_config, str) or not _SHA.fullmatch(camera_config):
            raise ValueError("Continue requires checkpoint camera_config_fingerprint as a 64-hex SHA256")
        if p["expected_config_fingerprint"] is not None and camera_config.lower() != p["expected_config_fingerprint"]:
            raise ValueError("Checkpoint camera configuration does not match the commissioned profile")
        _integer(saved.get("next_point_index"), "checkpoint next_point_index", 0, len(scan_plan.delays) - 1)
        _integer(saved.get("next_shot_index"), "checkpoint next_shot_index", 0, scan_plan.shots_per_point - 1)
        if "frame_counts" in saved:
            counts = saved["frame_counts"]
            if not isinstance(counts, list) or len(counts) != len(scan_plan.delays):
                raise ValueError("Checkpoint frame_counts must match positional scan rows")
            for count in counts:
                _integer(count, "checkpoint frame_count", 0, scan_plan.shots_per_point)
            pending = next((index for index, count in enumerate(counts)
                            if count < scan_plan.shots_per_point), None)
            if (pending is None or saved["next_point_index"] != pending
                    or saved["next_shot_index"] != counts[pending]
                    or any(counts[index] for index in range(pending + 1, len(counts)))):
                raise ValueError("Checkpoint counts disagree with the next positional point/shot")
    elif checkpoint is not None:
        raise ValueError("Only continue may bind a checkpoint")
    if saved and set(saved) & {"order_id", "acquisition_epoch", "config_fingerprint"}:
        raise ValueError("Checkpoint must not preassign camera-generated identifiers")
    output = _copy(output_context) if output_context is not None else None
    if output is not None and (not isinstance(output, dict) or set(output) != {"output_dir", "sample_name"}
                               or not all(isinstance(value, str) for value in output.values())
                               or not output["output_dir"].strip()):
        raise ValueError("output_context requires exact output_dir and sample_name strings")

    camera = hardware["andor_device"]
    stage = hardware["owis_aggregator_device"]
    dg = hardware["dg645_device"]
    targets = [{"device": camera, "command": command} for command in
               ("state", "V0Capabilities", "start_grabbing", "V0BeginOrder", "V0OrderStatus", "V0ReadOrder",
                "V0CancelOrder", "V0ReleaseOrder", "stop_grabbing")]
    targets += [{"device": stage, "command": command} for command in
                ("move_axis", "read_attribute:positions", "read_attribute:states", "stop_axis")]
    targets += [{"device": dg, "command": command} for command in
                (("scpi_write", "scpi_query") if policy == "apply_recall_then_verify" else ("scpi_query",))]
    body = {
        "schema": PLAN_SCHEMA, "run_action": run_action, "scan_plan": scan_plan.to_dict(),
        "hardware_config": hardware, "profile": p, "profile_sha256": _hash(p),
        "processing_mode": p["processing_mode"],
        "phase_classifier_version": p["classifier_version"],
        "track_order": p["tracks"], "frames_per_cycle": 3,
        "camera_batch_frames": 3 * scan_plan.shots_per_point,
        "camera_batch_rule": "three frames per remaining cycle at current point; retries acquire only missing accepted cycles",
        "phase_actuation": "none; source classification of measured ordered triplets",
        "invalid_triplet_policy": "source_All_true_fallback_quirk" if p["all_cycles"] else "reject_whole_physical_cycle",
        "retry_budget": {"unit": "rejected_cycles_per_point", "maximum": p["max_rejected_cycles"],
                         "maximum_order_requests_per_point": 1 + p["max_rejected_cycles"]},
        "camera_admission": {**p["camera_admission"], "track_order": p["tracks"],
                             "expected_config_fingerprint": p["expected_config_fingerprint"],
                             "capabilities": "read only after authorization; validate before orders",
                             "context": "require commissioned config fingerprint; freeze first admitted epoch/wavelengths; require every order to match",
                             "owned_grabbing": "start only if initially idle; stop only if started by this run",
                             "parameter_mutations": []},
        "dg645": {"schema": dg645.get("schema", "dg645-recall-snapshot-v1"),
                  "source_sha256": _hash(dg645), "recall": dg645, "policy": policy,
                  "apply_commands": [f"*RCL {slot}"] if policy == "apply_recall_then_verify" else [],
                  "expected_raw_queries": [{"command": command, "expected": queries[command]}
                                           for command in sorted(queries) if command != "*IDN?"],
                  "identity_query_excluded_from_timing_verification": "*IDN?",
                  "restore_snapshot_commands_executed": False},
        "delay_axis": axis, "targets": targets,
        "cleanup": [{"device": camera, "command": "V0CancelOrder", "when": "pending order"},
                    {"device": camera, "command": "V0ReadOrder", "when": "pending order; preserve packet journal"},
                    {"device": camera, "command": "V0ReleaseOrder", "when": "pending order after journaling"},
                    {"device": camera, "command": "stop_grabbing", "when": "this run started grabbing"},
                    {"device": stage, "command": "stop_axis", "axis": axis, "when": "after run-owned motion"}],
        "checkpoint": saved, "checkpoint_sha256": _hash(saved) if saved is not None else None,
        "output_context": output,
    }
    return TangoRunPlan(scan_plan, _canonical(p), _canonical(hardware), _canonical(dg645), _canonical(body))
