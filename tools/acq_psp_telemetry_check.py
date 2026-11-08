"""Read-only, RAM-only comparison of PSP scalar receipts and ACQ telemetry.

Run explicitly with --live on Everest. Reads the existing bounded PSP RAM FIFO
only to obtain per-channel receipt times/raw labels; retains one latest receipt
per label. Does not clear it, record history, send controls or load NI drivers.
Equal numbers are consistency evidence, not proof of identical hardware samples.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import json
import math
import time

from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS


PSP_DEVICE = "tango://10.20.30.202:10000/manip/general/PSP"
TELEMETRY_DEVICE = "tango://10.20.30.202:10000/elyse/acquisition/telemetry"
NUMERIC_TYPES = {"DBL", "SGL", "EB", "EW", "EL"} | {
    prefix + str(bits) for prefix in ("I", "U") for bits in (8, 16, 32, 64)
}


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _fields(snapshot):
    """Use exact native labels; never invent bank identity from ACH/OUT index."""
    result, unsupported, invalid = {}, {}, []
    for bank in BANKS:
        packet = snapshot.get("publications", {}).get(bank)
        if packet is None:
            continue
        descriptor = packet.get("lv_type", {}).get("contained_type") or {}
        fields, values = descriptor.get("fields"), packet.get("data")
        if descriptor.get("type") != "Cluster":
            unsupported[bank] = descriptor.get("type", "unknown")
            continue
        if not isinstance(fields, list) or not isinstance(values, list) or len(fields) != len(values):
            invalid.append(bank)
            continue
        for index, (field, value) in enumerate(zip(fields, values)):
            result[(bank, index)] = dict(
                label=field.get("name"), kind=field.get("type"), value=value,
                packet=packet,
            )
    return result, unsupported, invalid


def _same(left, right, kind, atol, rtol):
    if kind == "Boolean":
        return (type(left) is bool and type(right) is bool and left == right)
    return _finite(left) and _finite(right) and math.isclose(left, right, abs_tol=atol, rel_tol=rtol)


def compare_snapshots(before, receipts, after, *, now, max_age=2.0, atol=1e-9, rtol=1e-9):
    """Return metadata/counts only: no measured or commanded values in report."""
    for name, value in (("now", now), ("max_age", max_age), ("atol", atol), ("rtol", rtol)):
        if not _finite(value) or value < 0 or (name == "max_age" and value == 0):
            raise ValueError("invalid " + name)
    first, unsupported_before, invalid_before = _fields(before)
    last, unsupported_after, invalid_after = _fields(after)
    owners = defaultdict(set)
    for key, field in {**first, **last}.items():
        if isinstance(field["label"], str):
            owners[field["label"]].add(key)
    latest = {}
    numeric_receipts = [item["value"] for item in receipts if _finite(item.get("value"))]
    invalid_receipts = 0
    for receipt in receipts:
        label, stamp = receipt.get("raw_channel"), receipt.get("recv_ts")
        if not isinstance(label, str) or not _finite(stamp) or stamp > now:
            invalid_receipts += 1
            continue
        # Derived archive paths are not direct raw-cluster fields.
        if label not in owners:
            continue
        previous = latest.get(label)
        if previous is None or stamp > previous["recv_ts"] or (
            stamp == previous["recv_ts"] and receipt.get("id", 0) > previous.get("id", 0)
        ):
            latest[label] = receipt
    rows = []
    changed_receiver = before.get("receiver_session") != after.get("receiver_session")
    invalid_transport = any(
        snapshot.get("source") != "copied_labview_telemetry"
        or snapshot.get("hardware_writes") is not False
        or snapshot.get("storage_mode") != "ram_latest"
        or not isinstance(snapshot.get("receiver_session"), str)
        or not snapshot["receiver_session"]
        for snapshot in (before, after)
    )
    for bank, index in sorted(set(first) | set(last)):
        a, b = first.get((bank, index)), last.get((bank, index))
        label = (b or a)["label"]
        status = "missing_endpoint"
        if a is not None and b is not None:
            pa, pb = a["packet"], b["packet"]
            if invalid_transport:
                status = "invalid_transport_contract"
            elif changed_receiver or pa.get("session_id") != pb.get("session_id"):
                status = "session_changed"
            elif not isinstance(pa.get("session_id"), str) or not pa["session_id"]:
                status = "invalid_transport_contract"
            elif a["label"] != b["label"] or a["kind"] != b["kind"]:
                status = "schema_changed"
            elif any(p.get("producer_kind") != "copied_acquisition" for p in (pa, pb)):
                status = "not_copied_acquisition"
            elif any(p.get("error", {}).get("status") is not False for p in (pa, pb)):
                status = "telemetry_read_error"
            elif any(p.get("stale") is not False or not _finite(p.get("age_seconds"))
                     or not 0 <= p["age_seconds"] <= max_age for p in (pa, pb)):
                status = "telemetry_stale"
            elif len(owners[label]) != 1:
                status = "ambiguous_raw_label"
            elif a["kind"] not in NUMERIC_TYPES | {"Boolean"}:
                status = "unsupported_field_type"
            elif label not in latest:
                status = "no_recent_psp_receipt"
            elif now - latest[label]["recv_ts"] > max_age:
                status = "psp_stale"
            else:
                value = latest[label].get("value")
                if a["kind"] == "Boolean":
                    valid = (type(a["value"]) is bool and type(b["value"]) is bool
                             and _finite(value) and value in (0, 1))
                    converted = bool(value) if valid else None
                else:
                    valid = _finite(value) and _finite(a["value"]) and _finite(b["value"])
                    converted = value
                if not valid:
                    status = "invalid_numeric_value"
                elif not _same(a["value"], b["value"], a["kind"], atol, rtol):
                    status = "source_changing_not_same_sample"
                elif _same(b["value"], converted, b["kind"], atol, rtol):
                    status = "consistent_stationary_endpoints"
                else:
                    status = "different_values"
        rows.append(dict(bank=bank, index=index, raw_label=label, status=status))
    counts = Counter(row["status"] for row in rows)
    per_bank = {bank: dict(Counter(row["status"] for row in rows if row["bank"] == bank))
                for bank in BANKS}
    consistent = counts["consistent_stationary_endpoints"]
    return dict(
        verdict=("DIFFERENCES_OBSERVED" if counts["different_values"] else
                 "PARTIAL_CONSISTENCY" if consistent else "INCONCLUSIVE"),
        full_parity_verified=False, hardware_sample_identity_verified=False,
        hardware_commands_sent=0, storage_mode="ram_latest", values_in_report=False,
        absolute_tolerance=atol, relative_tolerance=rtol, max_age_seconds=max_age,
        fields_considered=len(rows), counts=dict(counts), per_bank=per_bank,
        unsupported_bank_types_before=unsupported_before,
        unsupported_bank_types_after=unsupported_after,
        invalid_schema_banks=sorted(set(invalid_before + invalid_after)),
        missing_banks_before=sorted(set(BANKS) - set(before.get("publications", {}))),
        missing_banks_after=sorted(set(BANKS) - set(after.get("publications", {}))),
        invalid_psp_receipts=invalid_receipts,
        recent_psp_receipts_examined=len(receipts),
        recent_numeric_psp_receipts=len(numeric_receipts),
        all_recent_numeric_psp_values_zero=(all(value == 0 for value in numeric_receipts)
                                           if numeric_receipts else None),
        changed_receiver_session=changed_receiver,
        receiver_session=after.get("receiver_session"),
        received_messages_before=before.get("received_this_process"),
        received_messages_after=after.get("received_this_process"),
        unmatched_or_unverified_fields=[row for row in rows if row["status"] != "consistent_stationary_endpoints"],
        limits=[
            "PSP receipts and telemetry controls are independently sampled, not atomic hardware shots.",
            "Stationary endpoints do not exclude an intermediate excursion.",
            "Bare labels shared by banks cannot establish source ownership.",
            "PSP Array/OpenG errors and unpublished banks require separate investigation.",
            "No output value here is a physical voltage readback or permission to actuate.",
        ],
    )


def capture_live(proxy_factory, *, max_age=2.0, wall_clock=time.time, mono_clock=time.monotonic):
    """Fixed read-only calls. No generic command dispatch, filesystem or archive."""
    if not _finite(max_age) or not 0 < max_age <= 10:
        raise ValueError("max_age must be in (0, 10] seconds")
    telemetry = proxy_factory(TELEMETRY_DEVICE)
    psp = proxy_factory(PSP_DEVICE)
    for proxy in (telemetry, psp):
        proxy.set_timeout_millis(5000)
    start = mono_clock()
    before = json.loads(telemetry.read_attribute("telemetry_json").value)
    before_received = mono_clock()
    receipts = json.loads(psp.command_inout("get_history_json", float(max_age)))
    after = json.loads(telemetry.read_attribute("telemetry_json").value)
    end = mono_clock()
    before = copy.deepcopy(before)
    for packet in before.get("publications", {}).values():
        if _finite(packet.get("age_seconds")):
            packet["age_seconds"] += max(0.0, end - before_received)
    report = compare_snapshots(before, receipts, after, now=wall_clock(), max_age=max_age)
    report["capture_duration_seconds"] = end - start
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Read fixed Everest Tango receivers; no writes")
    parser.add_argument("--max-age", type=float, default=2.0)
    args = parser.parse_args(argv)
    if not args.live:
        parser.error("--live is required; importing this tool performs no network access")
    if not math.isfinite(args.max_age) or not 0 < args.max_age <= 10:
        parser.error("--max-age must be in (0, 10] seconds")
    import tango

    report = capture_live(tango.DeviceProxy, max_age=args.max_age)
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
