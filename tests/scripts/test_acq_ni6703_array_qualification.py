"""Original NI6703 array arithmetic and rejected generated effects."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_lvkit import DEFAULT_CHECKOUT, verify_checkout  # noqa: E402

verify_checkout(DEFAULT_CHECKOUT)

from qualify_acq_ni6703_arrays import (  # noqa: E402
    audit_fragment,
    fragments,
    qualify,
    run_fragment,
)


class Ni6703ArrayQualificationTests(unittest.TestCase):
    def test_original_four_bank_numeric_fixture_agreement(self):
        result = qualify()
        receipt = result["receipt"]
        self.assertEqual(receipt["bank_cases"], 2068)
        self.assertEqual(receipt["scalar_values_compared"], 20680)
        for field in (
            "full_writer_qualified",
            "deployable",
            "hardware_executed",
            "vi_executed",
        ):
            self.assertFalse(receipt[field])

    def test_c8_offsets_keep_ten_fields_and_negative_entries(self):
        source = fragments()[0]["8"]
        self.assertIn("_lv.add(", source)
        bank = [0.0] * 10
        self.assertEqual(run_fragment(source, bank), [0.0, -2.0, -2.0] + [0.0] * 7)
        self.assertEqual(bank, [0.0] * 10)

    def test_historical_concatenation_is_rejected_before_execution(self):
        with self.assertRaises(AssertionError):
            audit_fragment("result = logical + [0.0, -2.0, -2.0]\n")

    def test_import_loop_or_hardware_attribute_is_rejected(self):
        for source in (
            "import socket\n",
            "while True: pass\n",
            "result = _lv.start(logical)\n",
            "result = _lv.add(logical, [0.0], extra=True)\n",
            "result = open('x')\n",
            "result = _lv.add.__globals__\n",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source)

    def test_other_shapes_representations_and_nonfinite_inputs_are_rejected(self):
        for logical in ([0.0] * 9, [0] * 10, (0.0,) * 10, [float("nan")] * 10):
            with self.subTest(logical=logical), self.assertRaises(AssertionError):
                run_fragment("result = logical\n", logical)


if __name__ == "__main__":
    unittest.main()
