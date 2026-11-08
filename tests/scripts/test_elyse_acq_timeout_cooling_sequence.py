"""Complete cooling graphs remain conditional on the source arm selection."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_timeout_cooling_sequence import checked_vam, unique, validate_cooling


class CoolingTimeoutSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def rejects(self, root):
        with self.assertRaises(AssertionError):
            validate_cooling(root, self.meta)

    def test_all_original_graphs_pass(self):
        self.assertIn("12 diagrams / 38 nets", validate_cooling(self.root, self.meta))

    def test_missing_enabled_metadata_not_fabricated(self):
        root = deepcopy(self.root)
        ET.SubElement(unique(root, "commentNode", "14478"), "activeDiag").text = "00"
        self.rejects(root)

    def test_sequence_order_and_restore_field_pinned(self):
        root = deepcopy(self.root)
        diagrams = unique(root, "sequence", "8256").find("diagramList")
        diagrams[0], diagrams[1] = diagrams[1], diagrams[0]
        self.rejects(root)
        root = deepcopy(self.root)
        unique(root, "nMux", "30840").find("termList/*[@uid='30959']/dco/i").text = "1"
        self.rejects(root)

    def test_inverted_compound_input_cannot_be_removed(self):
        root = deepcopy(self.root)
        unique(root, "cpdArith", "47240").find(
            "termList/*[@uid='47325']/dco/objFlags"
        ).text = "65536"
        self.rejects(root)

    def test_extra_error_gate_or_general_stop_rejected(self):
        root = deepcopy(self.root)
        ET.SubElement(
            unique(root, "diag", "31857").find("zPlaneList"),
            "SL__arrayElement",
            {"class": "select", "uid": "999999"},
        )
        self.rejects(root)

    def test_wait_and_special_snapshot_flags_pinned(self):
        root = deepcopy(self.root)
        unique(root, "diag", "14187").find(
            "nodeList/*/termList/*[@uid='15485']/dco/ConstValue"
        ).text = "00000096"
        self.rejects(root)
        root = deepcopy(self.root)
        unique(root, "gRef", "39313").find("termList/*/dco/objFlags").text = "1"
        self.rejects(root)


if __name__ == "__main__":
    unittest.main()
