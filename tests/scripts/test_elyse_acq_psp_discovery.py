"""PSP discovery source and rejecting mutations, without any network I/O."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_psp_discovery import checked_root, unique, validate_tree


class PSPDiscoveryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_root(REPOSITORY /
            "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip")

    def setUp(self):
        self.root = deepcopy(self.original)

    def test_original_passes(self):
        self.assertIn("final exterior error is unwired", validate_tree(self.root)[2])

    def test_namespace_change_rejected(self):
        frame = unique(self.root, "diag", "21518")
        node = frame.find("nodeList/*/termList/*[@uid='74407']/dco/ConstValue")
        node.text = node.text.replace("33302E32", "33302E33")
        with self.assertRaisesRegex(AssertionError, "namespace changed"):
            validate_tree(self.root)

    def test_filter_change_rejected(self):
        unique(self.root, "diag", "21518").find("nodeList/*/termList/*[@uid='74224']/dco/ConstValue").text = "000001"
        with self.assertRaisesRegex(AssertionError, "filter literals"):
            validate_tree(self.root)

    def test_error_seed_disconnected_rejected(self):
        unique(self.root, "diag", "21518").find("signalList/*/termList/*[@uid='74293']").set("uid", "74285")
        with self.assertRaisesRegex(AssertionError, "discovery frame wire set"):
            validate_tree(self.root)

    def test_reference_auto_indexing_removed_rejected(self):
        unique(self.root, "forLoop", "74267").find("termList/*[@uid='74279']/dco/TunnelType").text = "00"
        with self.assertRaisesRegex(AssertionError, "reference indexing"):
            validate_tree(self.root)

    def test_data_type_property_change_rejected(self):
        unique(self.root, "propNode", "74345").find("termList/*/dco/propList/*/PropItemCode").text = "18"
        with self.assertRaisesRegex(AssertionError, "data-type property"):
            validate_tree(self.root)

    def test_dynamic_open_type_input_swapped_rejected(self):
        unique(self.root, "sharedVariableDynamicOpen", "74325").find("termList/*[@uid='74342']/dco/terminal_ID").text = "0B"
        with self.assertRaisesRegex(AssertionError, "dynamic-open terminal"):
            validate_tree(self.root)

    def test_open_error_chain_break_rejected(self):
        unique(self.root, "diag", "74296").find("signalList/*/termList/*[@uid='74288']").set("uid", "74285")
        with self.assertRaisesRegex(AssertionError, "discovery body wire set"):
            validate_tree(self.root)

    def test_wait_change_rejected(self):
        unique(self.root, "diag", "74296").find("nodeList/*/termList/*[@uid='74305']/dco/ConstValue").text = "00000002"
        with self.assertRaisesRegex(AssertionError, "1-ms wait"):
            validate_tree(self.root)

    def test_shift_register_pairing_change_rejected(self):
        unique(self.root, "forLoop", "74267").find("termList/*[@uid='74293']/dco/rsrDCO").set("uid", "74290")
        with self.assertRaisesRegex(AssertionError, "shift-register pairing"):
            validate_tree(self.root)

    def test_reference_bank_write_becomes_read_rejected(self):
        unique(self.root, "gRef", "74186").find("termList/*/objFlags").text = "4096"
        with self.assertRaisesRegex(AssertionError, "writer/reader census"):
            validate_tree(self.root)

    def test_extra_reference_bank_reader_rejected(self):
        original = unique(self.root, "gRef", "74186")
        reader = deepcopy(original)
        reader.set("uid", "1234567")
        reader.find("termList/*/objFlags").text = "4096"
        self.root.find("root/zPlaneList").append(reader)
        with self.assertRaisesRegex(AssertionError, "writer/reader census"):
            validate_tree(self.root)

    def test_retry_guard_added_rejected(self):
        frame = unique(self.root, "diag", "74296")
        ET.SubElement(frame.find("zPlaneList"), "extra", {"class": "select", "uid": "1234567"})
        with self.assertRaisesRegex(AssertionError, "body operation census"):
            validate_tree(self.root)


if __name__ == "__main__":
    unittest.main()
