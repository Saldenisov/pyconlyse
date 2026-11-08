"""Analytical, parser, and failure-mode tests; run with python -m unittest."""

import io
import json
import unittest
from zipfile import ZipFile

import numpy as np
from utilities.dataio.laser_shot_correction import (
    RAW_GROUPS,
    CorrectionConfig,
    PairedOutlierConfig,
    correct_block,
    correct_scan,
    detect_paired_od_outliers,
    load_legacy_zip,
    parse_legacy_raw,
)
from utilities.dataio.measurement_correction import correct_measurement


def fixture(shots=5):
    wavelength = np.linspace(450.0, 750.0, 9)
    x = np.empty((6, shots, len(wavelength)))
    bg_ref, bg_sample = 100.0, 300.0
    x[0], x[3] = bg_ref, bg_sample
    x[1], x[2] = 10000.0 + bg_ref, 5000.0 + bg_sample
    x[4], x[5] = 8000.0 + bg_ref, 3200.0 + bg_sample
    return wavelength, x


def raw_text(wavelength, *blocks):
    lines = ["\t".join(map(str, wavelength))]
    for delay, block in blocks:
        lines.append("S_%.7f" % delay)
        for group in [0, 3, 1, 2, 4, 5]:
            lines.extend("\t".join(map(str, row)) for row in block[group])
        lines.append("E_")
    return "\n".join(lines)


class PairedOutlierTests(unittest.TestCase):
    def test_finite_bad_pair_is_removed_and_other_four_reaveraged(self):
        w, raw = fixture()
        wanted = np.array([-0.03, 0.033, 0.034, 0.032, 0.035])
        for j, value in enumerate(wanted):
            raw[5, j] = 300 + 4000 / (10**value)
        first = correct_block(raw, w)
        detection = detect_paired_od_outliers(first, w)
        np.testing.assert_array_equal(
            detection.excluded_shots, [True, False, False, False, False]
        )
        corrected = correct_block(
            raw,
            w,
            excluded_shots=detection.excluded_shots,
            exclusion_reason="paired_od_outlier",
        )
        self.assertEqual(corrected.valid_shot_count, 4)
        np.testing.assert_allclose(corrected.od, wanted[1:].mean(), atol=1e-14)
        self.assertEqual(corrected.reasons[0], ("paired_od_outlier",))

    def test_two_repeats_do_not_establish_consensus(self):
        w, raw = fixture(2)
        raw[5, 0] *= 2
        detection = detect_paired_od_outliers(correct_block(raw, w), w)
        self.assertFalse(detection.eligible)
        self.assertFalse(detection.excluded_shots.any())

    def test_one_spectral_pixel_does_not_reject_entire_shot(self):
        w, raw = fixture()
        raw[5, 0, 2] *= 10
        detection = detect_paired_od_outliers(correct_block(raw, w), w)
        self.assertFalse(detection.excluded_shots.any())

    def test_normal_repeat_scatter_keeps_all_shots(self):
        w, raw = fixture()
        raw[5] += np.arange(5)[:, None] * 5
        detection = detect_paired_od_outliers(correct_block(raw, w), w)
        self.assertFalse(detection.excluded_shots.any())

    def test_invalid_exclusion_vector_and_configuration(self):
        w, raw = fixture()
        with self.assertRaises(ValueError):
            correct_block(raw, w, excluded_shots=np.ones(5))
        with self.assertRaises(ValueError):
            PairedOutlierConfig(min_good_repeats=2)


class CorrectionTests(unittest.TestCase):
    def test_full_pipeline_keeps_delays_and_distinguishes_raw_and_estimates(self):
        w, base = fixture()
        blocks = []
        for j in range(20):
            raw = base.copy()
            raw[5] = 300 + 4000 / (10**0.04)
            if j == 5:
                raw[5, 0] = 300 + 4000 / (10**-0.03)
            if j == 8:
                raw[:] = 0
            if j == 12:
                raw[5] = 300 + 4000 / (10**-0.02)
            if j == 17:
                raw[:, 4] = 0
            blocks.append((j, raw))
        scan = parse_legacy_raw(raw_text(w, *blocks))
        result = correct_measurement(scan)
        np.testing.assert_allclose(result.od, 0.04, atol=1e-14)
        self.assertEqual(result.valid_shot_counts[5], 4)
        self.assertEqual(result.valid_shot_counts[8], 0)
        self.assertEqual(result.valid_shot_counts[17], 4)
        self.assertTrue(result.missing_correction.filled_mask[:, 8].all())
        self.assertTrue(result.temporal_correction.corrected_mask[:, 12].all())
        payload = result.to_payload()
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload["delay_ps"], list(map(float, range(20))))
        self.assertEqual(payload["finite_paired_outliers_one_based"][5], [1])
        self.assertFalse(payload["audit"]["estimated_values_are_measurements"])
        self.assertEqual(payload["audit"]["delays"][5]["valid_shots"], 4)
        self.assertEqual(
            payload["audit"]["delays"][8]["status"], "estimated_from_neighbors"
        )

    def test_one_absent_shot_averages_four_unequal_od_values(self):
        w, raw = fixture()
        wanted = np.asarray([0.01, 0.03, 0.07, 0.11])
        for j, value in enumerate(wanted):
            raw[5, j] = 300 + 4000 / (10**value)
        raw[:, 4] = 0
        result = correct_block(raw, w)
        self.assertEqual(result.valid_shot_count, 4)
        np.testing.assert_allclose(result.od, wanted.mean(), atol=1e-14)
        self.assertTrue((result.pixel_counts == 4).all())
        self.assertEqual(result.reasons[4], ("zero_filled_slot",))

    def test_dark_single_state_rejects_whole_paired_shot(self):
        w, raw = fixture()
        raw[4, 2] = raw[0, 2]
        raw[5, 2] = raw[3, 2]
        result = correct_block(raw, w)
        self.assertEqual(result.valid_shot_count, 4)
        self.assertTrue(np.isnan(result.shot_od[2]).all())
        np.testing.assert_allclose(result.od, np.log10(1.25))

    def test_zero_od_is_valid_when_laser_is_present(self):
        w, raw = fixture()
        raw[5] = 4000 + raw[3]
        result = correct_block(raw, w)
        self.assertEqual(result.valid_shot_count, 5)
        np.testing.assert_allclose(result.od, 0, atol=1e-14)

    def test_all_absent_keeps_delay_with_nan(self):
        w, raw = fixture()
        raw[:] = 0
        scan = parse_legacy_raw(raw_text(w, (14.0, raw)))
        result = correct_scan(scan)
        self.assertEqual(result.delays_ps.tolist(), [14.0])
        self.assertEqual(result.valid_shot_counts.tolist(), [0])
        self.assertTrue(np.isnan(result.od).all())
        self.assertFalse(np.isinf(result.od).any())

    def test_failed_delay_serializes_as_json_null(self):
        w, raw = fixture()
        raw[:] = 0
        result = correct_scan(parse_legacy_raw(raw_text(w, (14.0, raw))))
        payload = result.to_payload()
        json.dumps(payload, allow_nan=False)
        self.assertEqual(payload["od"][0], [None])
        self.assertEqual(payload["valid_shot_counts"], [0])

    def test_separate_detector_backgrounds_and_unsigned_input(self):
        w, raw = fixture()
        result = correct_block(raw.astype(np.uint16), w)
        np.testing.assert_allclose(result.od, np.log10(1.25), atol=1e-14)

    def test_negative_reference_is_rejected_without_unsigned_wraparound(self):
        w, raw = fixture()
        raw[1, 0] = 50
        result = correct_block(raw.astype(np.uint16), w)
        self.assertEqual(result.valid_shot_count, 4)
        self.assertIn("low_signal:reference_off", result.reasons[0])

    def test_pixel_zero_excludes_only_that_pair_at_that_pixel(self):
        w, raw = fixture()
        raw[1, 0, 0] = raw[0, 0, 0]
        result = correct_block(raw, w)
        self.assertEqual(result.valid_shot_count, 5)
        self.assertEqual(result.pixel_counts[0], 4)
        self.assertTrue((result.pixel_counts[1:] == 5).all())
        self.assertFalse(np.isinf(result.od).any())

    def test_nonfinite_raw_rejects_shot(self):
        w, raw = fixture()
        raw[1, 2, 0] = np.inf
        result = correct_block(raw, w)
        self.assertEqual(result.valid_shot_count, 4)
        self.assertEqual(result.reasons[2], ("nonfinite_raw",))

    def test_pulse_monitor_can_detect_absent_pump_with_normal_probe(self):
        w, raw = fixture()
        flags = np.asarray([True, False, True, True, True])
        result = correct_block(raw, w, pulse_present=flags)
        self.assertEqual(result.valid_shot_count, 4)
        self.assertEqual(result.reasons[1], ("pulse_monitor_absent",))
        with self.assertRaises(ValueError):
            correct_block(raw, w, pulse_present=np.ones(5))

    def test_averaging_modes_have_distinct_analytical_results(self):
        w, raw = fixture(2)
        raw[5, 0], raw[5, 1] = 2300, 6300
        individual = correct_block(raw, w)
        averaged = correct_block(
            raw, w, CorrectionConfig(averaging="od_from_mean_spectra")
        )
        np.testing.assert_allclose(individual.od, (np.log10(2) + np.log10(2 / 3)) / 2)
        np.testing.assert_allclose(averaged.od, 0, atol=1e-14)

    def test_no_input_mutation(self):
        w, raw = fixture()
        before = raw.copy()
        correct_block(raw, w)
        np.testing.assert_array_equal(raw, before)

    def test_explicit_state_background_adapter(self):
        w, raw = fixture()
        raw[2] = 5100
        raw[4] = 8300
        result = correct_block(raw, w, CorrectionConfig(background_mode="state"))
        np.testing.assert_allclose(result.od, np.log10(1.25))

    def test_positive_policy_masks_signed_noise_pixel(self):
        w, raw = fixture()
        raw[1, :, 0] = 50
        raw[2, :, 0] = 250
        legacy = correct_block(raw, w)
        positive = correct_block(raw, w, CorrectionConfig(ratio_policy="positive"))
        self.assertTrue(np.isfinite(legacy.od[0]))
        self.assertTrue(np.isnan(positive.od[0]))
        self.assertEqual(positive.pixel_counts[0], 0)

    def test_wrong_detection_band_fails_explicitly(self):
        w, raw = fixture()
        with self.assertRaises(ValueError):
            correct_block(raw, w, CorrectionConfig(detection_band_nm=(1000, 2000)))

    def test_large_signals_do_not_overflow_ratio(self):
        w, raw = fixture(1)
        raw[1], raw[2], raw[4], raw[5] = 1e300, 1e299, 1e298, 1e297
        result = correct_block(raw, w)
        np.testing.assert_allclose(result.od, 0, atol=1e-12)


class ParserTests(unittest.TestCase):
    def test_group_order_and_variable_shot_count(self):
        w, first = fixture(5)
        _, second = fixture(4)
        scan = parse_legacy_raw(raw_text(w, (-10, first), (25, second)))
        np.testing.assert_array_equal(scan.blocks[0], first)
        np.testing.assert_array_equal(scan.blocks[1], second)
        self.assertEqual(RAW_GROUPS, ("BG1", "Ir1", "Is1", "BG2", "Ir2", "Is2"))

    def test_uploaded_zip_bytes(self):
        w, block = fixture()
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("nested/measurement.raw", raw_text(w, (5, block)))
        scan = load_legacy_zip(stream.getvalue())
        np.testing.assert_array_equal(scan.blocks[0], block)

    def test_multiple_raw_files_require_member(self):
        stream = io.BytesIO()
        w, block = fixture()
        with ZipFile(stream, "w") as archive:
            for name in ("a.raw", "b.raw"):
                archive.writestr(name, raw_text(w, (5, block)))
        with self.assertRaises(ValueError):
            load_legacy_zip(stream.getvalue())
        self.assertEqual(
            load_legacy_zip(stream.getvalue(), "b.raw").source_name, "b.raw"
        )

    def test_truncated_block_rejected(self):
        w, block = fixture()
        text = raw_text(w, (5, block))
        with self.assertRaises(ValueError):
            parse_legacy_raw(text.rsplit("E_", 1)[0])
        lines = text.splitlines()
        with self.assertRaises(ValueError):
            parse_legacy_raw("\n".join(lines[:2] + lines[3:]))

    def test_nonnumeric_and_wrong_width_are_errors(self):
        w, block = fixture()
        lines = raw_text(w, (5, block)).splitlines()
        for invalid in ("1\t2", "bad\trow"):
            copy = lines.copy()
            copy[2] = invalid
            with self.assertRaises(ValueError):
                parse_legacy_raw("\n".join(copy))


if __name__ == "__main__":
    unittest.main()
