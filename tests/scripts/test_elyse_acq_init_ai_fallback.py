"""Offline mutation tests for the saved NI6071E startup fallback."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_cooling_start_completion import checked_root, unique
from validate_acq_initialization_ai_fallback import validate_tree


class AIFallbackEvidenceTests(unittest.TestCase):
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

    def test_added_error_code_comparison_is_rejected(self):
        frame = unique(self.root, "sequence", "201").find("diagramList")[2]
        node = deepcopy(frame.find("zPlaneList/*"))
        node.set("uid", "new-comparison")
        frame.find("zPlaneList").append(node)
        self.assert_rejected("selector logic")

    def test_clear_task_replaced_by_stop_is_rejected(self):
        unique(self.root, "iUse", "4034").find("label/textRec/text").text = '"DAQmx Stop Task.vi"'
        self.assert_rejected("fallback call 4034 changed")

    def test_task_bank_change_is_rejected(self):
        unique(self.root, "gRef", "8343").find("termList/*/dco/paramIdx").text = "21"
        self.assert_rejected("task-reference bank")

    def test_clear_chain_wire_change_is_rejected(self):
        frame = unique(self.root, "select", "2105").find("diagramList")[1]
        signal = next(s for s in frame.findall("signalList/*")
                      if {"4247", "8009"} <= {t.get("uid") for t in s.findall("termList/*")})
        signal.find("termList/*[@uid='8009']").set("uid", "wrong")
        self.assert_rejected("4247->8009")

    def test_sample_count_change_is_rejected(self):
        unique(self.root, "sRN", "2132").find(
            "termList/*[@uid='2390']/dco/ConstValue").text = "00000064"
        self.assert_rejected("literal 2390 changed")

    def test_trigger_destination_slot_change_is_rejected(self):
        unique(self.root, "iUse", "1198").find(
            "termList/*[@uid='1205']/dco/paramIdx").text = "7"
        self.assert_rejected("connector slot")

    def test_reinitialization_error_clear_replacement_is_rejected(self):
        unique(self.root, "iUse", "2268").find("label/textRec/text").text = '"Abort.vi"'
        self.assert_rejected("fallback call 2268 changed")

    def test_fallback_result_local_change_is_rejected(self):
        unique(self.root, "sLoc", "306").find("diagDefined").text = "01"
        self.assert_rejected("sequence-local mapping")


if __name__ == "__main__":
    unittest.main()
