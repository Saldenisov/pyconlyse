"""Build/check Python-3.4 stage data from hash-pinned ACQ wires, offline.

No LabVIEW, drivers, devices, PSP, network or live telemetry are accessed.
The output contains procedure intent, not operating permission/readiness.
"""
import argparse
import json
from pathlib import Path

from validate_acq_linear_procedures import validate_tree
from validate_acq_vam_status import checked_vam
from validate_acq_focal_helpers import checked_roots, validate_member, VALUES
from validate_acq_modulator_start_event_guards import ARCHIVE_SHA256
from validate_acq_timeout_dispatch import DISPATCH, validate_dispatch


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "legacy/xp_acq_agent/data/modulator_stage_catalog.json"
SOURCES = ROOT / "legacy/xp_acq_agent/data/source_exports"
# Operation, original ACQ event, Supervision DPS request field.
# These are independent requests, NOT an inferred startup prerequisite chain.
OPERATIONS = (
    ("cooling.start", 3, 0), ("cooling.stop", 4, 1),
    ("general.start", 5, 2), ("general.stop", 6, 3),
    ("chauffage.stop", 7, 5), ("prema.stop", 8, 7),
    ("relays_ht.stop", 9, 9), ("focales.stop", 10, 11),
    ("modulator.reset", 11, 12), ("chauffage.start", 12, 4),
    ("prema.start", 13, 6), ("relays_ht.start", 14, 8),
    ("focales.start", 15, 10), ("alimentation_ht.start", 20, 15),
    ("alimentation_ht.stop", 21, 17), ("alimentation_ht.reset", 22, 16),
)


def build():
    root, meta = checked_vam(SOURCES / "0_ACQ_ELYSE_XML_sha6fe8.zip")
    procedures = validate_tree(root, meta)
    validate_dispatch(root, meta)
    for name, event, dps in OPERATIONS:
        if DISPATCH[dps][-1] != event:
            raise AssertionError("DPS dispatch differs from stage catalog: " + name)
    focal = checked_roots(SOURCES / "ACQ_17_original_members_XML_20261001.zip")
    for enabled in (False, True):
        validate_member(focal["1_Focales " + ("ON" if enabled else "OFF") + ".vi"], enabled=enabled)
    result = dict(
        schema_version=1, source_archive_sha256=ARCHIVE_SHA256,
        scope="SAVED_PROCEDURE_INTENT_NOT_RUNTIME_OR_SAFETY_PERMISSION",
        hardware_enabled=False, source_frame_effects_unordered=True,
        procedures={name: dict(event=event, dps_request_field=dps, frames=procedures[event])
                    for name, event, dps in OPERATIONS},
        focal_helpers={
            "branches": [dict(focal=i, resource="COM" + str(13-i),
                              voltage_v=VALUES[i][0], current_slew=VALUES[i][1],
                              current_a=VALUES[i][2]) for i in (3, 2, 1)],
            "ordered_calls": ["Initialize", "Set Voltage", "Set Current Slew",
                              "Set Current", "Set Output", "Close"],
            "parallel_branches": True, "id_query": False, "reset": True,
            "output_on": {"1_Focales ON.vi": True, "1_Focales OFF.vi": False},
            "resources_are_saved_defaults_not_verified_ports": True,
            "unused_baud_literal_is_not_a_serial_configuration": True,
        },
    )
    # Normalize tuples exactly as they will be stored/read by Python 3.4.
    return json.loads(json.dumps(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    expected = build()
    if args.write:
        OUTPUT.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    if json.loads(OUTPUT.read_text("utf-8")) != expected:
        raise AssertionError("Python 3.4 stage catalog differs from original graph")
    print("PASS: 16 procedure requests, complete source frame effects, both three-Chroma helper graphs; no hardware/network I/O")


if __name__ == "__main__":
    main()
