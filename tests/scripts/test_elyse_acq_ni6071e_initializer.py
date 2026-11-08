"""Mutation tests for NI6071E initializer's non-actuating source contract."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_modulator_start_event_guards import unique
from validate_acq_ni6071e_initializer import checked_roots, validate_trees


class NI6071EInitializerEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_roots(
            REPOSITORY / "legacy/xp_acq_agent/data/source_exports/1_ACQ_INIT_NI6071E_XML_shafeb8.zip")

    def setUp(self):
        self.roots = deepcopy(self.original)
        self.bd = self.roots["vi_BDHb.xml"]

    def assert_rejected(self, message):
        with self.assertRaisesRegex(AssertionError, message):
            validate_trees(self.roots)

    def change_literal(self, frame_index, uid, value):
        frame = unique(self.bd, "sequence", "101").find("diagramList")[frame_index]
        frame.find(f"nodeList/*/termList/*[@uid='{uid}']/dco/ConstValue").text = value

    def test_saved_source_passes(self):
        self.assertEqual(len(validate_trees(self.roots)), 5)

    def test_connector_control_swap_is_rejected(self):
        self.roots["vi_FPHb.xml"].find(".//conPane/cons/*/ConnectionDCO").set("uid", "609")
        self.assert_rejected("connector assignments")

    def test_local_parameter_map_change_is_rejected(self):
        self.roots["vi.xml"].find("CPMp/Section/TypeDesc").set("Flags", "0x0000")
        self.assert_rejected("connector-to-local parameter map")

    def test_local_trigger_reference_swap_is_rejected(self):
        unique(self.bd, "gRef", "3428").find("termList/*/dco/paramIdx").text = "0"
        self.assert_rejected("local reference changed")

    def test_timing_source_change_is_rejected(self):
        self.change_literal(2, "3755", "000000072F322F50464930")
        self.assert_rejected("literal 3755 changed")

    def test_finite_to_continuous_change_is_rejected(self):
        self.change_literal(1, "3693", "00002723")
        self.assert_rejected("literal 3693 changed")

    def test_trigger_polarity_change_is_rejected(self):
        self.change_literal(2, "3684", "000027EF")
        self.assert_rejected("literal 3684 changed")

    def test_read_auto_start_change_is_rejected(self):
        self.change_literal(1, "3670", "0000")
        self.assert_rejected("literal 3670 changed")

    def test_task_auto_cleanup_change_is_rejected(self):
        self.change_literal(2, "3547", "0000")
        self.assert_rejected("literal 3547 changed")

    def test_c1_volts_units_change_is_rejected(self):
        self.change_literal(1, "3539", "00002751")
        self.assert_rejected("literal 3539 changed")

    def test_c2_volts_units_change_is_rejected(self):
        self.change_literal(2, "3384", "00002751")
        self.assert_rejected("literal 3384 changed")

    def test_volts_units_tunnel_indexing_change_is_rejected(self):
        tunnel = unique(self.bd, "forLoop", "2604").find("termList/*[@uid='2779']/dco")
        ET.SubElement(tunnel, "TunnelType").text = "01"
        self.assert_rejected("AI Volts units tunnel changed")

    def test_c2_channel_body_identity_change_is_rejected(self):
        unique(self.bd, "forLoop", "2604").find("diagramList")[0].set("uid", "2937")
        self.assert_rejected("AI channel body identity changed")

    def test_c1_sensitive_range_change_is_rejected(self):
        frame = unique(self.bd, "sequence", "101").find("diagramList")[1]
        literal = frame.find("nodeList/*/termList/*[@uid='1808']/dco/ConstValue")
        literal.text = literal.text.replace("3FA999999999999A", "3FF0000000000000")
        self.assert_rejected("per-channel range values")

    def test_channel_order_change_is_rejected(self):
        frame = unique(self.bd, "sequence", "101").find("diagramList")[2]
        literal = frame.find("nodeList/*/termList/*[@uid='982']/dco/ConstValue")
        literal.text = literal.text.replace("322F616930", "322F616931", 1)
        self.assert_rejected("ordered physical channel array")

    def test_channel_auto_index_disable_is_rejected(self):
        unique(self.bd, "forLoop", "2680").find(
            "termList/*[@uid='1351']/dco/TunnelType").text = "00"
        self.assert_rejected("auto-index tunnel")

    def test_error_shift_register_addition_is_rejected(self):
        unique(self.bd, "forLoop", "2604").find(
            "termList/*[@uid='2652']/dco").set("class", "lSR")
        self.assert_rejected("shift register")

    def test_added_error_feedback_wire_is_rejected(self):
        body = unique(self.bd, "forLoop", "2680").find("diagramList")[0]
        signal = ET.SubElement(body.find("signalList"), "SL__arrayElement", {"class": "signal"})
        terms = ET.SubElement(signal, "termList")
        ET.SubElement(terms, "SL__arrayElement", {"uid": "2693"})
        ET.SubElement(terms, "SL__arrayElement", {"uid": "2703"})
        self.assert_rejected("internal wire graph")

    def test_public_error_output_wire_addition_is_rejected(self):
        frame = unique(self.bd, "sequence", "101").find("diagramList")[2]
        signal = ET.SubElement(frame.find("signalList"), "SL__arrayElement", {"class": "signal"})
        terms = ET.SubElement(signal, "termList")
        ET.SubElement(terms, "SL__arrayElement", {"uid": "2814"})
        ET.SubElement(terms, "SL__arrayElement", {"uid": "1282"})
        self.assert_rejected("unconnected error terminal")

    def test_public_error_local_reference_addition_is_rejected(self):
        unique(self.bd, "gRef", "3454").find("termList/*/dco/paramIdx").text = "2"
        self.assert_rejected("local reference changed")

    def test_polymorphic_trigger_selection_change_is_rejected(self):
        unique(self.bd, "polyIUse", "2212").find("instanceSelector/menuInstanceUsed").text = "02"
        self.assert_rejected("polymorphic selection")

    def test_sample_frequency_connector_slot_change_is_rejected(self):
        unique(self.bd, "polyIUse", "2393").find(
            "termList/*[@uid='2411']/dco/paramIdx").text = "7"
        self.assert_rejected("connector slots")


if __name__ == "__main__":
    unittest.main()
