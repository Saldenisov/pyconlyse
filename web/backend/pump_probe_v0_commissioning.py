"""Offline BG/fingerprint evidence checks; never imports Tango or opens devices.

The darkest member of a triplet is a hypothesis, not an independent dark
control. A candidate profile always remains uncommissioned. Original files are
read only; an output bundle retains their exact transport headers and payloads.
"""

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import zlib

import h5py
import numpy as np

from DeviceServers.cameras.andor.v0_orders import config_fingerprint
from pump_probe_v0_tango import PACKET_SCHEMA, TRACK_ORDER, decode_tango_batch
from pump_probe_v0_tango_plan import validate_profile


SCHEMA = "v0-andor-bg-check-v1"
SNAPSHOT_SCHEMA = "v0-andor-capability-snapshot-v1"
MAX_PACKET_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_HEADER_BYTES = 2 * 1024 * 1024
I32_MIN, I32_MAX = -(2**31), 2**31 - 1
INDEPENDENT_BASES = {"independent_optical_control", "independent_trigger_timing"}


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _json_load(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("JSON values must be finite")

    return json.loads(data.decode("utf-8-sig") if isinstance(data, bytes) else data,
                      object_pairs_hook=pairs, parse_constant=constant)


def _local_path(value, base=None):
    text = str(value)
    if not text or text.startswith(("\\\\", "//")) or "://" in text:
        raise ValueError("Offline checks require an explicit local file path")
    path = Path(text).expanduser()
    path = ((base / path) if base is not None and not path.is_absolute() else path).resolve()
    if str(path).startswith(("\\\\", "//")):
        raise ValueError("Network paths are not read by offline checks")
    return path


def _digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path, limit):
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Input exceeds byte limit: " + str(path))
    return data


def _configuration(config, claimed):
    if not isinstance(config, dict):
        raise ValueError("Complete camera configuration is required")
    required = {"trigger_mode", "read_mode", "acquisition_mode", "track_count", "width",
                "exposure_seconds", "multi_track", "amplifier", "wavelengths", "axis_source"}
    if required - config.keys():
        raise ValueError("Missing camera sampling fields: " + ", ".join(sorted(required - config.keys())))
    if (config["trigger_mode"] != "ext" or config["read_mode"] != "multi_track"
            or config["acquisition_mode"] != "cont" or type(config["track_count"]) is not int
            or config["track_count"] != 2 or type(config["width"]) is not int
            or not 1 <= config["width"] <= 16384
            or config["axis_source"] not in {"configured_calibration", "linked_spectrograph"}):
        raise ValueError("Camera configuration is not the V0 external-trigger two-track readout")
    axis = config["wavelengths"]
    if (not isinstance(axis, list) or len(axis) != config["width"]
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in axis)):
        raise ValueError("Camera calibration must contain finite DBL wavelengths")
    exposure = config["exposure_seconds"]
    if type(exposure) not in (int, float) or not math.isfinite(exposure) or exposure <= 0:
        raise ValueError("Camera exposure must be positive and finite")
    for name in ("multi_track", "amplifier"):
        if not isinstance(config[name], list) or not config[name]:
            raise ValueError("Camera " + name + " readback is required")
    calculated = config_fingerprint(config)
    if claimed != calculated:
        raise ValueError("Camera sampling fingerprint disagrees with its configuration")
    return calculated


def check_snapshot(value, device, *, now):
    if not isinstance(value, dict) or value.get("schema") != SNAPSHOT_SCHEMA or value.get("device") != device:
        raise ValueError("Capability snapshot schema/device does not match the selected Andor")
    stamp = datetime.fromisoformat(str(value.get("captured_at_utc", "")).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Capability snapshot timestamp must include its timezone")
    caps = value.get("capabilities")
    if (not isinstance(caps, dict) or caps.get("schema") != PACKET_SCHEMA
            or caps.get("configuration_fresh") is not True or caps.get("external_trigger") is not True
            or caps.get("track_order") != TRACK_ORDER):
        raise ValueError("Snapshot lacks a fresh V0 camera configuration")
    fingerprint = _configuration(caps.get("configuration"), caps.get("config_fingerprint"))
    config = caps["configuration"]
    if any(caps.get(key) != config[key] for key in ("width", "track_count", "wavelengths", "read_mode", "trigger_mode")):
        raise ValueError("Capability summary disagrees with the full configuration")
    return {"config_fingerprint": fingerprint, "age_seconds": (now - stamp).total_seconds(),
            "captured_at_utc": stamp.isoformat(), "acquisition_active": caps.get("acquisition_active") is True,
            "runtime_admitted": caps.get("lossless") is True and not caps.get("admission_error"),
            "configuration": config,
            "optional_readbacks_unavailable": [k for k in ("image_mode_roi", "emccd_gain", "vertical_shift_speed",
                "horizontal_shift_speed", "image_indexing") if not isinstance(config.get(k), dict)
                or config[k].get("value") is None]}


def _i32_interval(background_upper, light_lower):
    """I32 k for max(BG) < float32(k) <= min(light), including rounding plateaus."""
    lo, hi = I32_MIN, I32_MAX + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if float(np.float32(mid)) > background_upper:
            hi = mid
        else:
            lo = mid + 1
    first = lo
    lo, hi = I32_MIN, I32_MAX + 1
    while lo < hi:
        mid = (lo + hi) // 2
        if float(np.float32(mid)) <= light_lower:
            lo = mid + 1
        else:
            hi = mid
    last = lo - 1
    return [first, last] if first <= last and first <= I32_MAX and last >= I32_MIN else None


def _packet_inputs(source, base):
    if not isinstance(source, dict):
        raise ValueError("Every source must be an object")
    if source.get("kind") == "packet":
        if set(source) != {"kind", "header_path", "payload_path"}:
            raise ValueError("Packet source requires kind/header_path/payload_path")
        header = _local_path(source["header_path"], base)
        payload = _local_path(source["payload_path"], base)
        raw_header, raw_packet = _read(header, MAX_HEADER_BYTES), _read(payload, MAX_PACKET_BYTES)
        yield raw_header, raw_packet, {str(header): hashlib.sha256(raw_header).hexdigest(),
                                      str(payload): hashlib.sha256(raw_packet).hexdigest()}
    elif source.get("kind") == "v0_h5":
        if set(source) - {"kind", "path", "order_ids"} or "path" not in source:
            raise ValueError("HDF5 source requires kind/path and optional order_ids")
        path = _local_path(source["path"], base)
        selected = source.get("order_ids")
        if selected is not None and (not isinstance(selected, list) or not selected
                or any(not isinstance(v, str) or not v for v in selected) or len(set(selected)) != len(selected)):
            raise ValueError("order_ids must be a nonempty unique string array")
        before = _digest(path)
        found, seen = set(), set()
        with h5py.File(path, "r") as handle:
            if "transport/accepted" not in handle or "transport/rejected" not in handle:
                raise ValueError("HDF5 has no original V0 transport packets; canonical RAW alone cannot qualify BG")
            for category in ("accepted", "rejected"):
                for record in handle[f"transport/{category}"].values():
                    entry = _json_load(record["envelope_json"].asstr()[()])
                    metadata = entry.get("metadata", {})
                    raw_header = metadata.get("raw_header")
                    if not isinstance(raw_header, str):
                        raise ValueError("Stored packet lacks its exact source header")
                    encoded_header = raw_header.encode("utf-8")
                    if len(encoded_header) > MAX_HEADER_BYTES:
                        raise ValueError("Stored source header exceeds byte limit")
                    order = _json_load(raw_header).get("order_id")
                    if selected is not None and order not in selected:
                        continue
                    found.add(order)
                    dataset = record["packet"]
                    if dataset.dtype != np.dtype("uint8") or dataset.ndim != 1 or dataset.size > MAX_PACKET_BYTES:
                        raise ValueError("Invalid stored original transport payload")
                    digest = entry.get("packet_sha256")
                    key = (order, hashlib.sha256(encoded_header).hexdigest(), digest, h5py.h5o.get_info(dataset.id).addr)
                    if key in seen:
                        continue
                    seen.add(key)
                    packet = dataset[...].tobytes()
                    if len(packet) != entry.get("packet_size") or hashlib.sha256(packet).hexdigest() != digest:
                        raise ValueError("Stored transport packet hash/length mismatch")
                    yield encoded_header, packet, {str(path): before}
        if _digest(path) != before:
            raise ValueError("Source HDF5 changed during the offline read")
        if selected is not None and found != set(selected):
            raise ValueError("Selected camera order was not found in HDF5")
    else:
        raise ValueError("Source kind must be packet or v0_h5")


def analyze_manifest(manifest_path, *, now=None):
    """Return a read-only analysis and exact packets for a new evidence bundle."""
    manifest_path = _local_path(manifest_path)
    raw_manifest = _read(manifest_path, MAX_HEADER_BYTES)
    manifest = _json_load(raw_manifest)
    fields = {"schema", "profile_path", "capabilities_path", "andor_device", "sources", "bg_labels",
              "minimum_cycles", "max_snapshot_age_seconds"}
    if not isinstance(manifest, dict) or set(manifest) != fields or manifest["schema"] != SCHEMA:
        raise ValueError("Invalid commissioning manifest schema/fields")
    minimum, ttl = manifest["minimum_cycles"], manifest["max_snapshot_age_seconds"]
    if type(minimum) is not int or not 30 <= minimum <= 2000:
        raise ValueError("minimum_cycles must be in 30..2000; this is coverage policy, not a confidence level")
    if type(ttl) is not int or not 1 <= ttl <= 3600:
        raise ValueError("max_snapshot_age_seconds must be in 1..3600")
    if not isinstance(manifest["sources"], list) or not 1 <= len(manifest["sources"]) <= 32:
        raise ValueError("Supply 1..32 real RAW sources")
    if not isinstance(manifest["andor_device"], str) or not manifest["andor_device"].strip():
        raise ValueError("Supply the exact Andor device name")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Analysis time must include its timezone")
    base = manifest_path.parent
    profile_path = _local_path(manifest["profile_path"], base)
    profile_data = _read(profile_path, MAX_HEADER_BYTES)
    profile = validate_profile(_json_load(profile_data))
    inputs = {str(manifest_path): hashlib.sha256(raw_manifest).hexdigest(), str(profile_path): hashlib.sha256(profile_data).hexdigest()}
    snapshot_path = _local_path(manifest["capabilities_path"], base)
    snapshot_data = _read(snapshot_path, MAX_HEADER_BYTES)
    inputs[str(snapshot_path)] = hashlib.sha256(snapshot_data).hexdigest()
    snapshot = check_snapshot(_json_load(snapshot_data), manifest["andor_device"], now=now)
    issues = []
    if not -5 <= snapshot["age_seconds"] <= ttl:
        issues.append("capability_snapshot_stale_or_future")
    labels = {}
    if not isinstance(manifest["bg_labels"], list):
        raise ValueError("bg_labels must be an array of independent frame annotations")
    for annotation in manifest["bg_labels"]:
        if (not isinstance(annotation, dict) or set(annotation) != {"order_id", "frame_ids", "basis", "evidence"}
                or not isinstance(annotation["basis"], str) or annotation["basis"] not in INDEPENDENT_BASES
                or not isinstance(annotation["evidence"], str) or not annotation["evidence"].strip()
                or not isinstance(annotation["order_id"], str) or not annotation["order_id"]
                or not isinstance(annotation["frame_ids"], list) or not annotation["frame_ids"]):
            raise ValueError("BG annotations need order_id/frame_ids/independent basis/nonempty evidence")
        for frame_id in annotation["frame_ids"]:
            key = (annotation["order_id"], frame_id)
            if type(frame_id) is not int or frame_id < 0 or key in labels:
                raise ValueError("BG annotations must name unique nonnegative SDK frame IDs")
            labels[key] = annotation
    packets, orders, used_ids, used_labels, rows, fingerprints, dtypes = [], {}, set(), set(), [], set(), set()
    total_bytes = 0
    for source in manifest["sources"]:
        for raw_header, packet, source_hashes in _packet_inputs(source, base):
            inputs.update(source_hashes)
            total_bytes += len(raw_header) + len(packet)
            if total_bytes > MAX_TOTAL_BYTES:
                raise ValueError("Selected RAW evidence exceeds 512 MiB")
            header = _json_load(raw_header)
            order = header.get("order_id")
            if not isinstance(order, str) or not order:
                raise ValueError("Packet has no order identity")
            identity = (hashlib.sha256(raw_header).hexdigest(), hashlib.sha256(packet).hexdigest())
            if order in orders:
                if orders[order] != identity:
                    raise ValueError("Same order ID has different original headers or payloads")
                continue
            orders[order] = identity
            packets.append((raw_header, packet))
            if len(packets) > 32:
                raise ValueError("Select at most 32 unique camera orders")
            try:
                fp = _configuration(header.get("configuration"), header.get("config_fingerprint"))
                fingerprints.add(fp)
                if fp != snapshot["config_fingerprint"]:
                    issues.append("RAW_configuration_differs_from_snapshot")
                frame_count = header.get("frame_count")
                if type(frame_count) is not int or frame_count % 3 or not 3 <= frame_count <= 600:
                    raise ValueError("Qualifying order requires 1..200 complete triplets")
                if (any(not isinstance(header.get(key), str) or not header[key] for key in ("run_id", "acquisition_epoch"))
                        or type(header.get("point_index")) is not int or header["point_index"] < 0):
                    raise ValueError("Packet lacks a valid run/epoch/point context")
                axis = header["configuration"]["wavelengths"]
                batch = decode_tango_batch((raw_header.decode("utf-8-sig"), packet),
                    order_id=order, run_id=header["run_id"], point_index=header["point_index"],
                    acquisition_epoch=header["acquisition_epoch"], config_fingerprint=fp,
                    wavelengths=axis, background_level=profile["background_level"], cycle_count=frame_count // 3)
                dtypes.add(header["dtype"])
                samples = np.frombuffer(zlib.decompress(packet), dtype=header["dtype"]).reshape(header["shape"])
                canonical = np.asarray(samples, dtype=np.float32)
                width = canonical.shape[-1]
                # Standard floating-point forward-error bound for any binary
                # SGL reduction tree with <=W-1 additions. Include underflow.
                n = width - 1
                gamma32 = n * 2.**-24 / (1. - n * 2.**-24)
                gamma64 = n * 2.**-53 / (1. - n * 2.**-53)
                exact = canonical[:, 1].astype(np.float64)
                total = exact.sum(axis=1)
                error = (gamma32 + gamma64) * np.abs(exact).sum(axis=1) + n * 2.**-150
                outcomes = [c.metadata for c in batch.cycles] + [c.metadata for c in batch.rejected]
                for outcome in sorted(outcomes, key=lambda c: c["packet_cycle_index"]):
                    index = outcome["packet_cycle_index"]
                    ids = header["frame_ids"][3*index:3*index+3]
                    for frame_id in ids:
                        key = (header["acquisition_epoch"], frame_id)
                        if key in used_ids:
                            raise ValueError("SDK frame IDs overlap across different orders")
                        used_ids.add(key)
                    sums = outcome["classification"]["detector_II_sums"]
                    annotated = [i for i, fid in enumerate(ids) if (order, fid) in labels]
                    if len(annotated) > 1:
                        raise ValueError("Multiple independently annotated BG frames in one triplet")
                    bg = annotated[0] if annotated else int(np.argmin(sums))
                    label = labels.get((order, ids[bg])) if annotated else None
                    if label:
                        used_labels.add((order, ids[bg]))
                    offset = 3 * index
                    lower = np.minimum(np.array(sums), total[offset:offset+3] - error[offset:offset+3])
                    upper = np.maximum(np.array(sums), total[offset:offset+3] + error[offset:offset+3])
                    rows.append({"order_id": order, "cycle_index": index, "frame_ids": ids,
                        "detector_II_sgl_sums": sums, "guarded_lower_sums": lower.tolist(), "guarded_upper_sums": upper.tolist(),
                        "BG_index": bg, "BG_frame_id": ids[bg],
                        "basis": label["basis"] if label else "darkest_triplet_hypothesis",
                        "evidence": label["evidence"] if label else None})
                    if len(rows) > 2000:
                        raise ValueError("Select at most 2000 calibration cycles")
            except (ValueError, KeyError, TypeError, zlib.error) as exc:
                issues.append("invalid_packet:" + order + ":" + str(exc))
    if set(labels) != used_labels:
        issues.append("BG_annotations_not_matched_to_qualifying_cycles")
    if len(rows) < minimum:
        issues.append("insufficient_cycle_coverage")
    if len(fingerprints) != 1:
        issues.append("mixed_or_missing_RAW_configuration")
    if len(dtypes) != 1:
        issues.append("mixed_or_missing_SDK_sample_dtype")
    labeled = sum(r["basis"] != "darkest_triplet_hypothesis" for r in rows)
    if labeled != len(rows) or not rows:
        issues.append("independent_BG_control_required")
    interval, guarded, proposed, margins = None, None, None, None
    if rows:
        bg_max = max(r["detector_II_sgl_sums"][r["BG_index"]] for r in rows)
        light_min = min(v for r in rows for i, v in enumerate(r["detector_II_sgl_sums"]) if i != r["BG_index"])
        interval = _i32_interval(bg_max, light_min)
        upper = max(r["guarded_upper_sums"][r["BG_index"]] for r in rows)
        lower = min(v for r in rows for i, v in enumerate(r["guarded_lower_sums"]) if i != r["BG_index"])
        guarded = _i32_interval(upper, lower)
        if guarded:
            proposed = guarded[0] + (guarded[1] - guarded[0]) // 2
            threshold = float(np.float32(proposed))
            margins = {"BG_upper_to_threshold": threshold - upper, "threshold_to_light_lower": lower - threshold}
        if not interval:
            issues.append("no_global_I32_threshold_separates_observed_BG_and_light")
        elif not guarded:
            issues.append("no_threshold_with_SGL_reduction_rounding_guard")
    def replay(level):
        if level is None:
            return None
        passed = 0
        counts = {"zero_BG": 0, "multiple_BG": 0, "wrong_BG": 0}
        for row in rows:
            candidates = [i for i, v in enumerate(row["detector_II_sgl_sums"]) if v < float(np.float32(level))]
            if candidates == [row["BG_index"]]:
                passed += 1
            elif not candidates:
                counts["zero_BG"] += 1
            elif len(candidates) > 1:
                counts["multiple_BG"] += 1
            else:
                counts["wrong_BG"] += 1
        return {"BG_level_I32": level, "SGL_threshold": float(np.float32(level)), "matched_cycles": passed, **counts}
    issues = list(dict.fromkeys(issues))
    report = {"schema": SCHEMA, "generated_at_utc": now.isoformat(), "hardware_access": False,
        "status": "ready_for_operator_review" if not issues and proposed is not None else "pending_or_blocked",
        "commissioned": False, "issues": issues, "andor_device": manifest["andor_device"],
        "snapshot": snapshot, "source_inputs": inputs, "unique_original_packets": len(packets),
        "cycle_count": len(rows), "independently_labeled_cycles": labeled, "minimum_cycles_policy": minimum,
        "coverage_is_not_a_statistical_confidence_claim": True,
        "observed_I32_interval_inclusive": interval, "guarded_I32_interval_inclusive": guarded,
        "proposed_BG_level": proposed, "guarded_margins": margins,
        "current_profile_replay": replay(profile["background_level"]), "candidate_replay": replay(proposed),
        "SDK_sample_dtypes": sorted(dtypes), "cycles": rows,
        "limits": ["Supplied snapshot freshness is checked; no live hardware state is attested by offline analysis.",
                   "Darkest-triplet classification is a hypothesis unless independently annotated.",
                   "Observed separation does not prove stability against future lamp/ADC/temperature drift.",
                   "The reduction guard covers standard IEEE SGL rounding; native execution and burst alignment remain separate checks.",
                   "Operator review, timing/control verification and explicit profile commissioning remain required."]}
    candidate = None
    blocking = [v for v in issues if v not in {"independent_BG_control_required", "insufficient_cycle_coverage"}]
    if proposed is not None and not blocking and len(fingerprints) == 1:
        candidate = dict(profile)
        candidate.update(commissioned=False, expected_config_fingerprint=next(iter(fingerprints)),
                         expected_sample_dtype=next(iter(dtypes)),
                         background_level=proposed, commissioning_status="candidate_only; independent_control_and_operator_review_required",
                         background_level_origin={"method": "offline_guarded_SGL_interval", "legacy_value": profile["background_level"],
                                                  "independently_labeled_cycles": labeled, "observed_cycles": len(rows)})
        candidate = validate_profile(candidate)
    # Detect source drift during the entire analysis, not just HDF5 iteration.
    if any(_digest(Path(path)) != digest for path, digest in inputs.items()):
        raise ValueError("Original input changed while preparing the evidence")
    return report, candidate, tuple(packets)


def write_bundle(output, report, candidate, packets):
    """Create a new directory; existing outputs and all input files are preserved."""
    output = _local_path(output)
    if candidate is not None and candidate.get("commissioned") is not False:
        raise ValueError("Evidence output must not activate a commissioned profile")
    output.mkdir(parents=False, exist_ok=False)
    evidence = output / "original_raw_packets.h5"
    with h5py.File(evidence, "x") as handle:
        pool = handle.create_group("packets")
        for index, (header, packet) in enumerate(packets):
            record = pool.create_group(f"{index:04d}")
            record.create_dataset("header_utf8", data=np.frombuffer(header, dtype=np.uint8))
            record.create_dataset("payload", data=np.frombuffer(packet, dtype=np.uint8))
            record.attrs["header_sha256"] = hashlib.sha256(header).hexdigest()
            record.attrs["payload_sha256"] = hashlib.sha256(packet).hexdigest()
        handle.flush()
        os.fsync(handle.id.get_vfd_handle())
    report = dict(report)
    report["original_RAW_archive"] = {"path": evidence.name, "sha256": _digest(evidence)}
    report_bytes = _json_bytes(report)
    if candidate is not None:
        candidate = dict(candidate)
        candidate["background_level_origin"] = {**candidate["background_level_origin"],
            "report_sha256": hashlib.sha256(report_bytes).hexdigest(), "RAW_archive_sha256": _digest(evidence)}
    for name, data in [("report.json", report_bytes)] + ([("profile.candidate.json", _json_bytes(candidate))] if candidate is not None else []):
        with (output / name).open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    return report
