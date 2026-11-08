"""Prepare/analyze local Andor commissioning evidence. No hardware commands."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web/backend"))

from pump_probe_v0_commissioning import (
    SCHEMA, SNAPSHOT_SCHEMA, _json_bytes, _json_load, _local_path,
    analyze_manifest, write_bundle,
)
from pump_probe_v0_tango_plan import validate_profile
from pump_probe_v0_config import DEFAULT_HARDWARE_CONFIG


def prepare(output, profile):
    output, profile = _local_path(output), _local_path(profile)
    profile_bytes = profile.read_bytes()
    validate_profile(_json_load(profile_bytes))
    output.mkdir(parents=False, exist_ok=False)
    manifest = {"schema": SCHEMA, "profile_path": "profile.input.json",
                "capabilities_path": "capabilities.snapshot.json",
                "andor_device": DEFAULT_HARDWARE_CONFIG["andor_device"], "sources": [], "bg_labels": [],
                "minimum_cycles": 30, "max_snapshot_age_seconds": 900}
    instructions = {
        "schema": SCHEMA, "status": "waiting_for_real_RAW_and_capability_snapshot",
        "hardware_access": False, "production_profile_changed": False,
        "source_profile": {"path": str(profile), "sha256": hashlib.sha256(profile_bytes).hexdigest()},
        "required_inputs": ["Original complete V0ReadOrder packets (header JSON + binary zlib payload), or V0 HDF5 transport records",
                            "Fresh V0Capabilities snapshot for the selected Andor device; obtain without changing camera parameters",
                            "Independent BG frame annotations from optical control or verified trigger timing"],
        "capability_snapshot_request": {
            "method": "POST", "path": "/api/pump-probe-v0/commissioning/andor-snapshot", "body": {},
            "save_response_field": "snapshot", "save_as": "capabilities.snapshot.json",
            "authorization": {"route_id": "v0.andor-snapshot", "action": "v0.andor-snapshot",
                "targets": [{"device": manifest["andor_device"], "command": "V0Capabilities"}],
                "args": {"andor_device": manifest["andor_device"], "readback": "V0Capabilities", "purpose": "BG_level_and_sampling_fingerprint"}},
            "commands_excluded": ["start_grabbing", "V0BeginOrder", "scpi_write", "move_axis", "camera parameter writes"],
            "precondition": "Configured Tango mode and idle V0 controller; shared experiment mutation lock; exact production readback authorization",
        },
        "source_examples": [
            {"kind": "packet", "header_path": "order.header.json", "payload_path": "order.payload.bin"},
            {"kind": "v0_h5", "path": "original_run.h5", "order_ids": ["select-real-order-id"]}],
        "BG_label_example": {"order_id": "select-real-order-id", "frame_ids": ["replace-with-integer-SDK-BG-frame-IDs"],
                             "basis": "independent_optical_control", "evidence": "Describe the independent no-light control/alignment"},
        "threshold_rule": "max(BG) < float32(I32 BG_level) <= min(Ie,I0), detector II, sequential SGL sums",
        "rounding_guard": "Also require separation under a W-1-addition IEEE float32 forward-error bound",
        "minimum_coverage": "30 distinct measured cycles is an operational coverage gate, not a statistical confidence claim",
        "review_boundary": "Darkest-triplet inference alone cannot commission a profile. Candidate remains commissioned=false.",
        "RAW_preservation": "Read-only input files, before/after SHA256 checks, exact header and payload archive in a new HDF5 file",
        "analyze_argv": [sys.executable, str(Path(__file__).resolve()), "analyze", "--manifest", str(output / "manifest.json"),
                         "--output", str(output.parent / (output.name + "-check"))],
        "snapshot_example_only": {"schema": SNAPSHOT_SCHEMA, "device": manifest["andor_device"],
                                  "captured_at_utc": "replace-with-actual-UTC-read-time", "capabilities": "replace-with-exact-V0Capabilities-JSON-object"},
    }
    for name, data in [("profile.input.json", profile_bytes), ("manifest.json", _json_bytes(manifest)),
                       ("preparation.json", _json_bytes(instructions))]:
        with (output / name).open("xb") as stream:
            stream.write(data)
    return {"status": instructions["status"], "prepared": str(output), "hardware_access": False,
            "commissioned": False, "analyze_argv": instructions["analyze_argv"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("prepare", help="Create a new local input manifest; no acquisition or profile activation")
    init.add_argument("--output", required=True)
    init.add_argument("--profile", default=str(ROOT / "web/pump_probe/config/v0_tango_raw_profile.json"))
    check = sub.add_parser("analyze", help="Check original local RAW and a supplied capability snapshot")
    check.add_argument("--manifest", required=True)
    check.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.output, args.profile)
            code = 0
        else:
            report, candidate, packets = analyze_manifest(args.manifest)
            saved = write_bundle(args.output, report, candidate, packets)
            result = {"status": saved["status"], "report": str(_local_path(args.output) / "report.json"),
                      "proposed_BG_level": saved["proposed_BG_level"], "issues": saved["issues"],
                      "cycle_count": saved["cycle_count"], "commissioned": False, "hardware_access": False,
                      "candidate_profile": str(_local_path(args.output) / "profile.candidate.json") if candidate else None}
            code = 0 if saved["status"] == "ready_for_operator_review" else 2
        print(json.dumps(result, indent=2, allow_nan=False))
        return code
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "input_error", "error": str(exc), "hardware_access": False,
                          "commissioned": False}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
