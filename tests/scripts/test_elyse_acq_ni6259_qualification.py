"""The generated fragment execution grammar excludes I/O and imports."""

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_ni6259_dormant import audit_fragment, qualify


class QualificationTests(unittest.TestCase):
    def test_narrow_array_grammar_accepts_only_supplied_mean_arrays(self):
        for source in (
            "result = means\n",
            "product = _lv.mul(means, [5.0, 1.0])\n"
            "result = _lv.add(product, [10.0, 0.0])\n",
        ):
            with self.subTest(source=source):
                self.assertTrue(audit_fragment(source).body)

    def test_import_io_unbound_names_and_mutation_are_rejected(self):
        for source in (
            "import socket\nresult = means\n",
            "result = _lv.read(means, [])\n",
            "result = _lv.mul(means, unknown)\n",
            "means = []\nresult = means\n",
            "result = _lv.mul(means, [], unexpected=1)\n",
            "result = _lv.mul(means, float('nan'))\n",
            "result = [v for v in means]\n",
            "result = means[0]\n",
            "result = _lv.__dict__\n",
            "a, result = means\n",
            "result = [True]\n",
            "result = [1e999]\n",
            "result = _lv.mul\nresult = means\n",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source)

    def test_current_shared_converter_matches584_bounded_array_cases(self):
        receipt = qualify()
        self.assertEqual(receipt["fixture_counts"], {"False": 292, "True": 292})
        self.assertEqual(receipt["array_cases"], 584)
        self.assertEqual(
            receipt["fixture_sha256"],
            "338CB56DA72FD596ECEA62C09A6FF6B34CF6EA2971CC5A23194E28C8C6442287",
        )
        self.assertFalse(receipt["native_mean_qualified"])
        self.assertFalse(receipt["hardware_executed"])
        self.assertFalse(receipt["vi_executed"])
        self.assertFalse(receipt["deployable"])
        self.assertFalse(receipt["whole_acquisition_qualified"])


if __name__ == "__main__":
    unittest.main()
