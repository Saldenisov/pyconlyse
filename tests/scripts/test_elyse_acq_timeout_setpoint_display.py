"""Nested field indices must be traced, not used as top-level ordinals."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_timeout_setpoint_display import checked_vam, unique, validate_display


class SetpointDisplaySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_passes(self):
        self.assertIn(
            "20 nested Consigne copies", validate_display(self.root, self.meta)
        )

    def test_raw_nested_index_not_replaced_by_top_level_ordinal(self):
        root = deepcopy(self.root)
        unique(root, "nMux", "10562").find("termList/*[@uid='10568']/dco/i").text = "3"
        with self.assertRaises(AssertionError):
            validate_display(root, self.meta)

    def test_source_field_and_wire_mutation_rejected(self):
        root = deepcopy(self.root)
        unique(root, "nMux", "24000").find("termList/*[@uid='24014']/dco/i").text = "9"
        with self.assertRaises(AssertionError):
            validate_display(root, self.meta)
        root = deepcopy(self.root)
        unique(root, "diag", "10526").find("signalList/*/termList/*").set(
            "uid", "999999"
        )
        with self.assertRaises(AssertionError):
            validate_display(root, self.meta)


if __name__ == "__main__":
    unittest.main()
