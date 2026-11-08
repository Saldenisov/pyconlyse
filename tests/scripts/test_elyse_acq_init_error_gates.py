"""Offline mutation tests for Acquisition initialization error handling."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_cooling_start_completion import checked_root, unique
from validate_acq_initialization_error_gates import validate_tree


class InitializationGateEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_root(
            REPOSITORY / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.root = deepcopy(self.original)

    def assert_rejected(self, message):
        with self.assertRaisesRegex(AssertionError, message):
            validate_tree(self.root)

    def test_saved_source_passes(self):
        self.assertEqual(len(validate_tree(self.root)), 4)

    def test_added_top_level_operation_is_rejected(self):
        frame = unique(self.root, "sequence", "201").find("diagramList")[1]
        node = deepcopy(frame.find("zPlaneList/*"))
        node.set("uid", "added-operation")
        frame.find("zPlaneList").append(node)
        self.assert_rejected("top-level operations")

    def test_error_arm_call_replacement_is_rejected(self):
        unique(self.root, "iUse", "383").find("label/textRec/text").text = '"Stop Task.vi"'
        self.assert_rejected("called VI changed")

    def test_gate_output_to_next_initializer_change_is_rejected(self):
        frame = unique(self.root, "sequence", "201").find("diagramList")[1]
        signal = next(s for s in frame.findall("signalList/*")
                      if {"374", "436"} <= {t.get("uid") for t in s.findall("termList/*")})
        signal.find("termList/*[@uid='436']").set("uid", "wrong")
        self.assert_rejected("374->436")

    def test_added_no_error_operation_is_rejected(self):
        gate = unique(self.root, "select", "1242")
        gate.find("diagramList")[0].find("zPlaneList").append(
            deepcopy(gate.find("diagramList")[1].find("zPlaneList/*")))
        self.assert_rejected("no-error arm")

    def test_task_reference_destination_change_is_rejected(self):
        unique(self.root, "gRef", "1053").find("termList/*/dco/paramIdx").text = "46"
        self.assert_rejected("local-reference set")

    def test_sequence_local_definition_change_is_rejected(self):
        unique(self.root, "sLoc", "1063").find("diagDefined").text = "02"
        self.assert_rejected("sequence-local frame mapping")

    def test_reader_destination_call_change_is_rejected(self):
        unique(self.root, "iUse", "287").find("label/textRec/text").text = '"Wrong Reader.vi"'
        self.assert_rejected("reader error-input destination")

    def test_case_arm_order_change_is_rejected(self):
        unique(self.root, "select", "1503").find("SelectRangeArray32/*/diagramIdx").text = "1"
        self.assert_rejected("Case arms changed")


if __name__ == "__main__":
    unittest.main()
