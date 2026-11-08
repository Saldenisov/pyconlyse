"""All23 procedure gates including historically disputed magnet-zero wrapper."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_event_envelopes import ROWS, checked_vam, unique, validate_envelopes


class EventEnvelopeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_all_original_event_envelopes_pass(self):
        self.assertIn(
            "72 event/gate diagrams / 73 nets", validate_envelopes(self.root, self.meta)
        )

    def test_each_newval_field_cannot_be_oldval(self):
        for row in ROWS:
            with self.subTest(event=row[0]):
                root = deepcopy(self.root)
                unique(root, "eventDataNode", row[4]).find(
                    f"termList/*[@uid='{row[5]}']/dco/i"
                ).text = "5"
                with self.assertRaises(AssertionError):
                    validate_envelopes(root, self.meta)

    def test_magnet_zero_gate_cannot_be_removed(self):
        root = deepcopy(self.root)
        frame = unique(root, "diag", "38732")
        node = frame.find("zPlaneList/*[@uid='38772']")
        frame.find("zPlaneList").remove(node)
        with self.assertRaises(AssertionError):
            validate_envelopes(root, self.meta)

    def test_special_event25_flag_cannot_be_normalized(self):
        root = deepcopy(self.root)
        unique(root, "eventStruct", "43").findall("EventNodeEvents/*")[25].find(
            "regFlags"
        ).text = "1"
        with self.assertRaises(AssertionError):
            validate_envelopes(root, self.meta)


if __name__ == "__main__":
    unittest.main()
