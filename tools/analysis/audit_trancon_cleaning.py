"""Compare generated cleaning with a NumPy oracle on saved TRANCON OD maps.

This audit models Experiment's SGL storage explicitly. Quantiles select stress
test thresholds; they are not part of the ported cleaning algorithm.
No native execution, experiment writes, or device access occurs.
"""

import argparse
import csv
import hashlib
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from legacy.trancon_client.candidates.cleaning import experiment_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dat_paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = []
    for path in args.dat_paths:
        path = path.resolve(strict=True)
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        saved = np.loadtxt(path)
        delays = saved[0, 1:]
        data = saved[1:, 1:].T.astype(np.float32).astype(np.float64)
        if data.shape[1] < 200 or len(delays) != data.shape[0]:
            raise ValueError("Audit window requires at least 200 wavelengths and matching delays")
        with np.errstate(invalid="ignore"):
            kin = data[:, 100:200].mean(axis=1)
        finite = kin[np.isfinite(kin)]
        lower, upper = np.quantile(finite, [.15, .85])
        flags = np.flatnonzero((kin < lower) | (kin > upper))
        for mode in ("delete", "approx"):
            output = experiment_candidate(data.tolist(), delays.tolist(), (100, 199),
                                          (0, len(delays)-1), (float(lower), float(upper)), mode)
            if mode == "delete":
                expected = np.delete(data, flags, axis=0)
                expected_delays = np.delete(delays, flags)
            else:
                expected = data.copy()
                expected_delays = delays.copy()
                with np.errstate(invalid="ignore", over="ignore"):
                    for index in flags:
                        if index == 0:
                            expected[index] = expected[index+1]
                        elif index == len(data)-1:
                            expected[index] = expected[index-1]
                        else:
                            expected[index] = (expected[index-1] + expected[index+1]) / 2.
            actual = np.asarray(output.data)
            if actual.shape != expected.shape:
                raise AssertionError(f"Axis shape mismatch: {actual.shape} != {expected.shape}")
            np.testing.assert_equal(output.timedelays, expected_delays)
            np.testing.assert_equal(output.kinetics, kin)
            masks = {"nan": np.isnan, "positive_inf": np.isposinf, "negative_inf": np.isneginf}
            differences = {name + "_mask_mismatches": int((predicate(actual) != predicate(expected)).sum())
                           for name, predicate in masks.items()}
            common = np.isfinite(actual) & np.isfinite(expected)
            error = float(np.abs(actual[common] - expected[common]).max(initial=0))
            if error != 0 or any(differences.values()):
                raise AssertionError(f"Cleaning oracle mismatch: error={error}, masks={differences}")
            if hashlib.sha256(path.read_bytes()).hexdigest() != fingerprint:
                raise AssertionError("Source archive changed during audit")
            records.append({"path": str(path), "source_sha256": fingerprint,
                            "mode": mode, "source_delay_count": len(delays),
                            "wavelength_count": data.shape[1], "selected_wavelength_pixels": "100..199",
                            "od_lower_bound": float(lower), "od_upper_bound": float(upper),
                            "flagged_delay_count": len(flags), "output_delay_count": len(actual),
                            "output_wavelength_count": actual.shape[1],
                            "max_finite_abs_error_od": error, **differences,
                            "delay_axis_equal": True, "source_unchanged": True,
                            "storage_precision": "SGL converted to DBL", "native_execution": False})
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"{len(records)} archive/mode comparisons: exact finite values and nonfinite masks")


if __name__ == "__main__":
    main()
