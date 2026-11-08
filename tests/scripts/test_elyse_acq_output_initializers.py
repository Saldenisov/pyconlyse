"""Original-source and rejecting mutation checks for output initializers."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_output_initializers import checked_roots, validate_ao, validate_dio, unique


class OutputInitializerEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_roots(REPOSITORY /
            "legacy/xp_acq_agent/data/source_exports/ACQ_17_original_members_XML_20261001.zip")

    def setUp(self):
        self.ao = deepcopy(self.original["1_ACQ_INIT_NI6703.vi"])
        self.dio = deepcopy(self.original["1_ACQ_INIT_DIO96.vi"])

    def mutate_constant(self, roots, uid, value):
        roots["vi_BDHb.xml"].find(
            f".//*[@class='diag']/nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue").text = value

    def test_original_dio_passes(self):
        self.assertIn("continuous public error chain", validate_dio(self.dio))

    def test_original_ao_passes(self):
        self.assertIn("C9 last-channel error only", validate_ao(self.ao))

    def test_dio_error_chain_break_rejected(self):
        self.dio["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='1837']").set("uid", "1838")
        with self.assertRaisesRegex(AssertionError, "DIO initializer wire set"):
            validate_dio(self.dio)

    def test_dio_input_range_change_rejected(self):
        self.mutate_constant(self.dio, "2008", "00000009332F706F7274303A35")
        with self.assertRaisesRegex(AssertionError, "string 2008"):
            validate_dio(self.dio)

    def test_dio_output_range_change_rejected(self):
        self.mutate_constant(self.dio, "2036", "0000000A342F706F7274373A3131")
        with self.assertRaisesRegex(AssertionError, "string 2036"):
            validate_dio(self.dio)

    def test_dio_input_becomes_output_rejected(self):
        unique(self.dio["vi_BDHb.xml"], "polyIUse", "579").find("instanceSelector/menuInstanceUsed").text = "24"
        with self.assertRaisesRegex(AssertionError, "polymorphic"):
            validate_dio(self.dio)

    def test_dio_auto_cleanup_false_rejected(self):
        self.mutate_constant(self.dio, "1204", "00")
        with self.assertRaisesRegex(AssertionError, "auto cleanup"):
            validate_dio(self.dio)

    def test_dio_task_field_swap_rejected(self):
        unique(self.dio["vi_BDHb.xml"], "nMux", "939").find("termList/*/dco[@uid='407']/i").text = "3"
        with self.assertRaisesRegex(AssertionError, "field order"):
            validate_dio(self.dio)

    def test_dio_extra_write_operation_rejected(self):
        ET.SubElement(self.dio["vi_BDHb.xml"].find("root/zPlaneList"), "extra", {"class": "prim", "uid": "1234567"})
        with self.assertRaisesRegex(AssertionError, "operation census"):
            validate_dio(self.dio)

    def test_ao_create_task_error_wiring_rejected(self):
        frame = unique(self.ao["vi_BDHb.xml"], "diag", "1241")
        frame.find("signalList/*/termList/*[@uid='725']").set("uid", "2521")
        with self.assertRaisesRegex(AssertionError, "AO frame 0 wire set"):
            validate_ao(self.ao)

    def test_ao_channel_error_seed_rejected(self):
        body = unique(self.ao["vi_BDHb.xml"], "diag", "773")
        body.find("signalList/*/termList/*[@uid='860']").set("uid", "885")
        with self.assertRaisesRegex(AssertionError, "AO channel body 0 wire set"):
            validate_ao(self.ao)

    def test_ao_range_change_rejected(self):
        self.mutate_constant(self.ao, "1359", "C014000000000000")
        with self.assertRaisesRegex(AssertionError, "range/default/units"):
            validate_ao(self.ao)

    def test_ao_terminal_configuration_mislabel_rejected(self):
        label = unique(self.ao["vi_BDHb.xml"], "diag", "773").find(
            "nodeList/*/termList/*[@uid='1765']/dco/ddo/partsList/"
            "*[@class='label']/textRec/text")
        label.text = '"DAC reference"'
        with self.assertRaisesRegex(AssertionError, "terminal-configuration label"):
            validate_ao(self.ao)

    def test_ao_loop_bound_change_rejected(self):
        self.mutate_constant(self.ao, "4898", "00000010")
        with self.assertRaisesRegex(AssertionError, "bound is not ten"):
            validate_ao(self.ao)

    def test_ao_physical_channel_change_rejected(self):
        node = unique(self.ao["vi_BDHb.xml"], "diag", "1824").find("nodeList/*/termList/*[@uid='1419']/dco/ConstValue")
        node.text = node.text.replace("382F616F39", "382F616F38")
        with self.assertRaisesRegex(AssertionError, "physical channel array"):
            validate_ao(self.ao)

    def test_ao_error_exit_indexed_rejected(self):
        tunnel = unique(self.ao["vi_BDHb.xml"], "forLoop", "789").find("termList/*[@uid='801']/dco")
        ET.SubElement(tunnel, "TunnelType").text = "01"
        with self.assertRaisesRegex(AssertionError, "indexing/error exit"):
            validate_ao(self.ao)

    def test_ao_error_shift_register_added_rejected(self):
        unique(self.ao["vi_BDHb.xml"], "forLoop", "714").find("termList/*[@uid='725']/dco").set("class", "rSR")
        with self.assertRaisesRegex(AssertionError, "accumulation topology"):
            validate_ao(self.ao)

    def test_ao_frames_reordered_rejected(self):
        frames = unique(self.ao["vi_BDHb.xml"], "sequence", "784").find("diagramList")
        first = frames[0]
        frames.remove(first)
        frames.append(first)
        with self.assertRaisesRegex(AssertionError, "sequence order"):
            validate_ao(self.ao)

    def test_ao_cross_frame_error_local_changed_rejected(self):
        unique(self.ao["vi_BDHb.xml"], "sLoc", "1970").find("diagDefined").text = "02"
        with self.assertRaisesRegex(AssertionError, "cross-frame error"):
            validate_ao(self.ao)

    def test_ao_task_cluster_field_swap_rejected(self):
        unique(self.ao["vi_BDHb.xml"], "nMux", "4818").find("termList/*/dco[@uid='4825']/i").text = "2"
        with self.assertRaisesRegex(AssertionError, "task cluster field"):
            validate_ao(self.ao)

    def test_ao_hidden_error_local_rejected(self):
        unique(self.ao["vi_BDHb.xml"], "gRef", "2198").find("termList/*/dco/paramIdx").text = "1"
        with self.assertRaisesRegex(AssertionError, "non-task local alias"):
            validate_ao(self.ao)

    def test_ao_public_error_control_swap_rejected(self):
        unique(self.ao["vi_BDHb.xml"], "fPTerm", "1282").find("dco").set("uid", "580")
        with self.assertRaisesRegex(AssertionError, "public terminal identity"):
            validate_ao(self.ao)

    def test_ao_extra_output_write_rejected(self):
        frame = unique(self.ao["vi_BDHb.xml"], "diag", "355")
        ET.SubElement(frame.find("zPlaneList"), "extra", {"class": "prim", "uid": "1234567"})
        with self.assertRaisesRegex(AssertionError, "operation census"):
            validate_ao(self.ao)


if __name__ == "__main__":
    unittest.main()
