"""Differential tests for lvkit-generated TRANCON functions, without devices.

NumPy is an independent arithmetic oracle, not native LabVIEW execution.
Archived DAT agreement additionally requires an explicit zero-slot policy.
"""

import argparse
import copy
import csv
import hashlib
import sys
import unittest
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legacy.trancon_client import log_transmission, raw_background, raw_data, scale
from legacy.trancon_client.raw_data import devtrancondependeciesaverage_array_poly as average


def oracle(raw, extra_bg=(0, 0)):
    raw = np.asarray(raw, dtype=np.float64)
    bg_i, bg_ii, ie_i, ie_ii, i0_i, i0_ii = np.moveaxis(raw, 1, 0)
    with np.errstate(all="ignore"):
        ratio = ((i0_i - bg_i - extra_bg[0]) / (ie_i - bg_i - extra_bg[0])) / (
            (i0_ii - bg_ii - extra_bg[1]) / (ie_ii - bg_ii - extra_bg[1]))
        return np.log10(ratio).mean(axis=1)


def equal(test, actual, expected, atol=2e-15):
    actual, expected = np.asarray(actual), np.asarray(expected)
    test.assertEqual(actual.shape, expected.shape)
    for classification in (np.isnan, np.isposinf, np.isneginf, np.isfinite):
        np.testing.assert_array_equal(classification(actual), classification(expected))
    finite = np.isfinite(expected)
    np.testing.assert_allclose(actual[finite], expected[finite], rtol=0, atol=atol)


class GeneratedNumericTests(unittest.TestCase):
    def test_average_order_and_shot_index(self):
        values = np.array([0, 0, 1, 1, 1, 1]).reshape(1, 6, 1, 1)
        values = np.repeat(values, 2, axis=2)
        values[0, 4, 1, 0] = 4
        result = raw_data(values.tolist()).exp_data
        equal(self, result, [[np.log10(4) / 2]])
        self.assertGreater(abs(result[0][0] - np.log10(2.5)), 0.09)

    def test_detector_background_pairing(self):
        values = np.array([10, 90, 110, 190, 210, 140]).reshape(1, 6, 1, 1)
        equal(self, raw_data(values.tolist()).exp_data, [[np.log10(4)]])

    def test_signed_ratio_and_nonfinite_pixels(self):
        # Positive raw counts generate negative corrected signals and exact zeros.
        columns = [[10, 10, 11, 11, 12, 12], [10, 10, 11, 11, 9, 12],
                   [10, 10, 11, 11, 10, 12], [10, 10, 10, 11, 12, 12],
                   [10, 10, 10, 10, 12, 12], [10, 10, 9, 9, 8, 8],
                   [0, 0, 0, 0, 0, 0]]
        values = np.asarray(columns).T.reshape(1, 6, 1, len(columns))
        actual = raw_data(values.tolist()).exp_data
        equal(self, actual, oracle(values))
        self.assertTrue(np.isnan(actual[0][1]))
        self.assertTrue(np.isneginf(actual[0][2]))
        self.assertTrue(np.isposinf(actual[0][3]))
        self.assertEqual(actual[0][5], 0.0)  # two negative ratios remain admissible

    def test_random_rectangular_counts(self):
        rng = np.random.default_rng(1032026)
        values = rng.integers(100, 65536, size=(5, 6, 7, 11), dtype=np.int32)
        values[:, :2] = rng.integers(0, 100, size=(5, 2, 7, 11))
        equal(self, raw_data(values.tolist()).exp_data, oracle(values))

    def test_precalculated_bypass_and_no_mutation(self):
        # The nonempty precalculated branch must not inspect malformed RAW.
        values, precalc = [["unused RAW"]], [[1.25, float("nan")]]
        before = copy.deepcopy(values)
        result = raw_data(values, precalc).exp_data
        self.assertIs(result, precalc)
        self.assertEqual(values, before)
        values = np.arange(1, 1 + 2 * 6 * 3 * 4).reshape(2, 6, 3, 4).tolist()
        before = copy.deepcopy(values)
        raw_data(values)
        self.assertEqual(values, before)

    def test_empty_lists(self):
        self.assertEqual(raw_data().exp_data, [])
        self.assertEqual(raw_data([[[] for _ in range(6)]][0:1]).exp_data, [[]])
        self.assertEqual(log_transmission().output_logxlog1x, [])
        self.assertEqual(scale().data_corrected, [])

    def test_negative_log_transmission(self):
        values = [1, 0.25, 0.0, -0.0, -1, float("inf"), -float("inf"), float("nan")]
        with np.errstate(all="ignore"):
            expected = np.log10(1 / np.asarray(values))
        equal(self, log_transmission(values).output_logxlog1x, expected)

    def test_scale_rows(self):
        values = [[1.0, -3.0, float("nan")], [float("inf"), 0.0, -float("inf")]]
        with np.errstate(all="ignore"):
            expected = np.asarray(values) * -2.5
        equal(self, scale(-2.5, values).data_corrected, expected)
        with np.errstate(all="ignore"):
            expected = np.asarray(values) * 0.0
        equal(self, scale(0.0, values).data_corrected, expected)

    def test_raw_background_separate_loop_accumulators(self):
        values = np.random.default_rng(73).integers(1, 30, (3, 6, 5, 9)).tolist()
        equal(self, raw_background(values, [7, -3]).data_corrected, oracle(values, (7, -3)))
        equal(self, raw_background(values, []).data_corrected, oracle(values))

    def test_unloaded_polymorphic_variant_raises(self):
        with self.assertRaises(NotImplementedError):
            average.average_2darray_sd_int([[1, 2]])
        with self.assertRaises(NotImplementedError):
            average.average_1darray_sd([1, 2])


def audit_generated(zip_paths, output):
    # Reuse the already qualified, shot-preserving disk parser, not the web preview.
    from audit_trancon_saved_pairs import compare, read_raw, reconstructed_od
    records = []
    for zip_path in zip_paths:
        zip_path = zip_path.resolve(strict=True)
        dat_path = zip_path.with_suffix(".dat")
        zip_payload, dat_payload = zip_path.read_bytes(), dat_path.read_bytes()
        with ZipFile(BytesIO(zip_payload)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".raw")]
            raw_name = next(name for name in names if Path(name).stem == zip_path.stem)
            raw_payload = archive.read(raw_name)
        _, _, disk = read_raw(raw_payload)
        if not np.equal(disk, np.trunc(disk)).all() or disk.min() < 0 or disk.max() > 65535:
            raise AssertionError("Archived RAW exceeds qualified I32 count domain")
        disk = disk.astype(np.int32)
        saved = np.loadtxt(StringIO(dat_payload.decode("utf-8-sig").replace(",", ".")))[1:, 1:].T
        for policy in ("signed_all", "signed_drop_zero"):
            inputs = disk.tolist() if policy == "signed_all" else [
                block[:, ~(block == 0).all(axis=(0, 2)), :].tolist() for block in disk]
            actual = np.asarray(raw_data(inputs).exp_data)
            oracle_result = reconstructed_od(disk.astype(np.float64), policy)
            oracle_check = compare(oracle_result, actual, 2e-15)
            if oracle_check["pixel_class_mismatches"] or oracle_check["common_finite_pixels_exceeding_tolerance"]:
                raise AssertionError(f"Generated/NumPy discrepancy: {zip_path.name}, {policy}")
            record = {"zip_path": str(zip_path), "policy": policy,
                      "zip_sha256": hashlib.sha256(zip_payload).hexdigest(),
                      "dat_sha256": hashlib.sha256(dat_payload).hexdigest(),
                      "raw_entry_sha256": hashlib.sha256(raw_payload).hexdigest(),
                      "whole_zero_slots": int((disk == 0).all(axis=(1, 3)).sum()),
                      "native_execution": False, "native_screenshots_verified": False,
                      "numpy_max_abs_error": oracle_check["max_common_finite_abs_error_od"],
                      "numpy_mask_mismatches": oracle_check["pixel_class_mismatches"],
                      **compare(saved, actual, 5.1e-5)}
            records.append(record)
            if policy == "signed_drop_zero" and (
                    record["pixel_class_mismatches"] or record["common_finite_pixels_exceeding_tolerance"]):
                raise AssertionError(f"DAT mismatch: {zip_path.name}")
            print(f"{zip_path.name}; {policy}; finite={record['computed_finite_pixels']}; "
                  f"DAT class differences={record['pixel_class_mismatches']}; "
                  f"NumPy max error={record['numpy_max_abs_error']:.12g}")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path,
                        default=ROOT / "docs/data-treatment/TRANCON_GENERATED_PAIR_AUDIT_2026-10-03.csv")
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(GeneratedNumericTests))
    if not result.wasSuccessful():
        return 1
    if args.zip:
        audit_generated(args.zip, args.output)
    print(f"tests={result.testsRun}; native_execution=False; native_screenshots_verified=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
