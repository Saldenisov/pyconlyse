"""Compare archived TRANCON RAW/ZIP against same-basename DAT, without devices.

The signed expression follows Raw_data_to_data.vi's division order exactly.
This executes reconstructed arithmetic in Python, not the original LabVIEW VI.
Only the modern S_/E_ RAW layout is accepted. Input files are never modified.
"""

import argparse
import csv
import hashlib
import sys
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from pump_probe_v0_data import parse_dat_payload, parse_zip_payload


def sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def read_raw(payload):
    lines = payload.decode("utf-8-sig").replace(",", ".").splitlines()
    if not lines or lines[0].startswith("Comments:"):
        raise ValueError("Audit supports modern S_/E_ RAW only")
    wavelengths = np.loadtxt(StringIO(lines[0]), ndmin=1)
    delays, blocks, rows = [], [], []
    delay = None
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line.startswith("S_"):
            if delay is not None:
                raise ValueError("RAW delay block lacks E_ marker")
            delay, rows = float(line[2:]), []
        elif line.startswith("E_"):
            if delay is None or not rows:
                raise ValueError("Empty or unmatched RAW delay block")
            values = np.loadtxt(StringIO("\n".join(rows)), ndmin=2)
            if values.shape[1] != wavelengths.size or values.shape[0] % 6:
                raise ValueError("RAW dimensions disagree with six-group layout")
            # Disk: BGI, BGII, IeI, IeII, I0I, I0II; preserve shot slots.
            blocks.append(values.reshape(6, -1, wavelengths.size))
            delays.append(delay)
            delay, rows = None, []
        else:
            if delay is None:
                raise ValueError("RAW values outside a delay block")
            rows.append(line)
    if delay is not None or not blocks:
        raise ValueError("Incomplete or empty RAW")
    return wavelengths, np.asarray(delays), np.stack(blocks)


def reconstructed_od(disk, policy):
    result = np.full((disk.shape[0], disk.shape[-1]), np.nan)
    for index, block in enumerate(disk):
        keep = np.ones(block.shape[1], dtype=bool)
        if policy != "signed_all":
            keep = ~(block == 0).all(axis=(0, 2))
        if not keep.any():
            continue
        bg_i, bg_ii, ie_i, ie_ii, i0_i, i0_ii = block[:, keep]
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            # Algebraic rearrangement changes NaN/Inf behavior at zeros.
            ratio = ((i0_i - bg_i) / (ie_i - bg_i)) / (
                (i0_ii - bg_ii) / (ie_ii - bg_ii)
            )
            if policy == "absolute_drop_zero":
                ratio = np.abs(ratio)
            result[index] = np.log10(ratio).mean(axis=0)
    return result


def compare(expected, actual, tolerance):
    common = np.isfinite(expected) & np.isfinite(actual)
    difference = np.abs(expected[common] - actual[common])
    masks = {
        "finite": np.isfinite,
        "nan": np.isnan,
        "positive_inf": np.isposinf,
        "negative_inf": np.isneginf,
    }
    record = {
        "saved_finite_pixels": int(np.isfinite(expected).sum()),
        "computed_finite_pixels": int(np.isfinite(actual).sum()),
        "common_finite_pixels": int(common.sum()),
        "max_common_finite_abs_error_od": float(difference.max()) if difference.size else "",
        "common_finite_pixels_exceeding_tolerance": int((difference > tolerance).sum()),
    }
    any_mismatch = np.zeros(expected.shape, dtype=bool)
    for label, mask in masks.items():
        mismatch = mask(expected) != mask(actual)
        record[label + "_mask_mismatches"] = int(mismatch.sum())
        any_mismatch |= mismatch
    record["pixel_class_mismatches"] = int(any_mismatch.sum())
    return record


def audit_pair(zip_path, tolerance):
    zip_path = zip_path.resolve(strict=True)
    dat_path = zip_path.with_suffix(".dat").resolve(strict=True)
    zip_payload, dat_payload = zip_path.read_bytes(), dat_path.read_bytes()
    with ZipFile(BytesIO(zip_payload)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".raw")]
        expected_name = zip_path.stem + ".raw"
        raw_name = next((n for n in names if Path(n).name == expected_name), names[0])
        raw_payload = archive.read(raw_name)
    wavelengths, delays, disk = read_raw(raw_payload)
    dat = np.loadtxt(StringIO(dat_payload.decode("utf-8-sig").replace(",", ".")))
    saved_wavelengths, saved_delays, saved_od = dat[1:, 0], dat[0, 1:], dat[1:, 1:].T
    if saved_od.shape != (disk.shape[0], disk.shape[-1]):
        raise ValueError("DAT and RAW map dimensions differ")
    wave_error = float(np.max(np.abs(wavelengths - saved_wavelengths)))
    delay_error = float(np.max(np.abs(delays - saved_delays)))
    axes_match = wave_error <= tolerance and delay_error <= tolerance

    # Check existing preview loader alongside shot-preserving audit parser.
    web_raw = parse_zip_payload(str(zip_path), zip_payload)
    web_dat = parse_dat_payload(str(dat_path), dat_payload)
    preview_axes_match = all(
        np.allclose(web_raw[key], values, rtol=0, atol=tolerance)
        and np.allclose(web_dat[key], values, rtol=0, atol=tolerance)
        for key, values in (("wavelengths", wavelengths), ("delays", delays))
    )
    zero_slots = (disk == 0).all(axis=(1, 3))
    base = {
        "zip_path": str(zip_path), "zip_sha256": sha256(zip_payload),
        "dat_path": str(dat_path), "dat_sha256": sha256(dat_payload),
        "raw_entry": raw_name, "raw_entry_sha256": sha256(raw_payload),
        "native_execution": False, "python_version": sys.version.split()[0],
        "numpy_version": np.__version__, "audit_script_sha256": sha256(Path(__file__).read_bytes()),
        "preview_loader_sha256": sha256((ROOT / "web/backend/pump_probe_v0_data.py").read_bytes()),
        "delays": disk.shape[0], "wavelengths": disk.shape[-1],
        "groups": disk.shape[1], "stored_shot_slots_per_delay": disk.shape[2],
        "total_pixels": saved_od.size, "whole_zero_shot_slots": int(zero_slots.sum()),
        "delays_with_zero_slots": int(zero_slots.any(axis=1).sum()),
        "zero_slot_delay_indices": ";".join(map(str, np.flatnonzero(zero_slots.any(axis=1)))),
        "axes_match": axes_match, "max_wavelength_axis_error_nm": wave_error,
        "max_delay_axis_error_ps": delay_error, "web_preview_axes_match": preview_axes_match,
        "web_preview_raw_trace_count": web_raw["raw_trace_count"],
        "web_preview_channel_keys": ";".join(c["key"] for c in web_raw["channels"]),
        "absolute_tolerance": tolerance,
    }
    records = []
    for policy in ("signed_all", "signed_drop_zero", "absolute_drop_zero"):
        actual = reconstructed_od(disk, policy)
        records.append({**base, "policy": policy, **compare(saved_od, actual, tolerance)})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip_paths", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=5.1e-5,
                        help="DAT rounding allowance (OD and axis comparisons)")
    args = parser.parse_args()
    if args.tolerance <= 0:
        parser.error("--tolerance must be positive")
    records = [record for path in args.zip_paths for record in audit_pair(path, args.tolerance)]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    failures = 0
    for record in records:
        if record["policy"] == "signed_drop_zero":
            passed = (record["axes_match"] and record["web_preview_axes_match"]
                      and record["pixel_class_mismatches"] == 0
                      and record["common_finite_pixels_exceeding_tolerance"] == 0)
            failures += not passed
            print(f"{Path(record['zip_path']).name}: {'PASS' if passed else 'FAIL'}; "
                  f"finite={record['saved_finite_pixels']}; "
                  f"zero_slots={record['whole_zero_shot_slots']}; "
                  f"max_error={record['max_common_finite_abs_error_od']:.12g}")
    print(f"pairs={len(args.zip_paths)}; failures={failures}; native_execution=False")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
