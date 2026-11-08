"""Read-only comparison of Python NI inputs and the copied LabVIEW telemetry.

One latest snapshot per source, in RAM only. No initialization, commands,
output readback claims, history file or automatic LabVIEW restart.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
import time
from pathlib import Path

from DeviceServers.control.elyse_acq.runtime_client import read_runtime


REFERENCE_DEVICE = "elyse/acquisition/telemetry"
INPUT_BANKS = (
    ("C1_NI6071E_AI", "C1NI6071E", "analog_input", 64),
    ("C2_NI6071E_AI", "C2NI6071E", "analog_input", 64),
    ("C3_DIO96_DI", "C3_IN_DIO96", "digital_input", 56),
    ("C4_DIO96_DI", "C4_IN_DIO96", "digital_input", 64),
    ("C5_DIO96_DI", "C5_IN_DIO96", "digital_input", 56),
)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def load_input_labels(path=None):
    path = Path(path or Path(__file__).resolve().parents[1] /
                "legacy/xp_acq_agent/data/channel_map.csv")
    groups = {row[1] for row in INPUT_BANKS}
    labels = {}
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["group"] not in groups:
                continue
            key = (row["group"], int(row["index"]))
            if key in labels:
                raise ValueError("Duplicate channel-map identity")
            labels[key] = "{0:02d} {1} {2} {3}".format(
                key[1], row["logical_code"], row["connector_pin"], row["description"])
    expected = {(group, index) for _, group, _, count in INPUT_BANKS for index in range(count)}
    if set(labels) != expected:
        raise ValueError("Channel map must cover all 304 directly published inputs")
    return labels


def compare_inputs(runtime, reference, labels, *, max_age=2.0, atol=1e-9, rtol=1e-9):
    """Counts only. Stale/synthetic values can never become verified matches."""
    if (not _finite(max_age) or max_age <= 0 or not _finite(atol) or atol < 0
            or not _finite(rtol) or rtol < 0):
        raise ValueError("Invalid comparison tolerances/freshness bound")
    latest = runtime.get("latest") or {}
    python_valid = (
        runtime.get("state") == "RUNNING" and runtime.get("stale") is False
        and not runtime.get("error") and runtime.get("storage_mode") == "ram_latest"
        and _finite(runtime.get("age_seconds")) and 0 <= runtime["age_seconds"] <= max_age
        and latest.get("source") == "python_daqmx_acquisition"
        and latest.get("simulated") is False
    )
    reference_valid = (reference.get("source") == "copied_labview_telemetry"
                       and reference.get("storage_mode") == "ram_latest")
    counts, per_bank = Counter(), {}
    unmatched = []
    for python_bank, labview_bank, kind, count in INPUT_BANKS:
        bank = latest.get("banks", {}).get(python_bank, {})
        values = bank.get("legacy_scaled_values" if kind == "analog_input" else "values")
        packet = reference.get("publications", {}).get(labview_bank, {})
        descriptor = packet.get("lv_type", {}).get("contained_type") or {}
        fields, old_values = descriptor.get("fields"), packet.get("data")
        shape_valid = (bank.get("kind") == kind and isinstance(values, list)
                       and len(values) == count)
        old_shape_valid = (descriptor.get("type") == "Cluster" and descriptor.get("name") == labview_bank
                           and isinstance(fields, list) and len(fields) == count
                           and isinstance(old_values, list) and len(old_values) == count)
        fresh_reference = (packet.get("stale") is False and _finite(packet.get("age_seconds"))
                           and 0 <= packet["age_seconds"] <= max_age)
        rows = Counter()
        label_matches = 0
        for index in range(count):
            expected_kind = "DBL" if kind == "analog_input" else "Boolean"
            field_matches = (old_shape_valid and fields[index].get("name") == labels[(labview_bank, index)]
                             and fields[index].get("type") == expected_kind)
            label_matches += bool(field_matches)
            if not python_valid:
                status = "python_not_current_hardware_data"
            elif not reference_valid or packet.get("producer_kind") != "copied_acquisition":
                status = "invalid_reference_source"
            elif not shape_valid or not old_shape_valid or not field_matches:
                status = "schema_mismatch"
            elif packet.get("error", {}).get("status") is not False:
                status = "reference_read_error"
            elif not fresh_reference:
                status = "reference_stale"
            else:
                current, previous = values[index], old_values[index]
                if kind == "digital_input":
                    valid = type(current) is bool and type(previous) is bool
                    same = valid and current == previous
                else:
                    valid = _finite(current) and _finite(previous)
                    same = valid and math.isclose(current, previous, abs_tol=atol, rel_tol=rtol)
                status = "invalid_scalar" if not valid else "consistent_values" if same else "different_values"
            rows[status] += 1
            if status != "consistent_values":
                unmatched.append(dict(bank=labview_bank, index=index, status=status))
        counts.update(rows)
        per_bank[labview_bank] = dict(count=count, exact_native_labels=label_matches,
                                     reference_age_seconds=packet.get("age_seconds"), counts=dict(rows))
    return dict(
        verdict="DIFFERENCES_OBSERVED" if counts["different_values"] else
                "PARTIAL_CONSISTENCY" if counts["consistent_values"] else "INCONCLUSIVE",
        full_parity_verified=False, hardware_sample_identity_verified=False,
        fields_considered=304, counts=dict(counts), per_bank=per_bank,
        python_state=runtime.get("state"), python_sequence=runtime.get("sequence"),
        python_resource_count=runtime.get("resource_count"),
        unmatched_fields=unmatched, values_in_report=False, storage_mode="ram_latest",
        absolute_tolerance=atol, relative_tolerance=rtol, max_age_seconds=max_age,
        unmapped_python_banks=["C11_NI6220_AI: 16 raw AI values; no direct bank in the 27 publications"],
        limits=["Independent sequential reads, not identical hardware samples",
                "Stale LabVIEW values are never counted as matches",
                "AO/DO startup command echoes are not physical output readback",
                "Derived DPS/EPS/status/pressure banks are not compared by this input-only tool"],
    )


def capture_live(database, proxy_factory):
    proxy = proxy_factory(REFERENCE_DEVICE)
    proxy.set_timeout_millis(3000)
    key_path = database.get_device_property(REFERENCE_DEVICE, ["key_file"])["key_file"]
    if len(key_path) != 1:
        raise ValueError("Expected one configured telemetry key file")
    key = Path(key_path[0]).read_bytes().strip()
    started = time.monotonic()
    runtime = read_runtime(key, timeout=2)
    reference_started = time.monotonic()
    reference = json.loads(proxy.read_attribute("telemetry_json").value)
    ended = time.monotonic()
    # Conservative upper bounds include request/response transit time.
    if _finite(runtime.get("age_seconds")):
        runtime["age_seconds"] += ended - started
    for packet in reference.get("publications", {}).values():
        if _finite(packet.get("age_seconds")):
            packet["age_seconds"] += ended - reference_started
    return compare_inputs(runtime, reference, load_input_labels())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--details", action="store_true", help="Include one diagnostic status per unmatched field")
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live required; import does not access network or cards")
    import tango
    report = capture_live(tango.Database(), tango.DeviceProxy)
    if not args.details:
        report.pop("unmatched_fields")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
