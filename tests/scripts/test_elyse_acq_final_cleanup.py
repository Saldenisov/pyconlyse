"""Reject changes to saved final-cleanup wiring; no hardware is imported."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_final_cleanup import (
    checked_root,
    checked_tpg_roots,
    unique,
    validate_cleanup_tree,
    validate_tpg_trees,
)


class FinalCleanupEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = (
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )
        cls.original = checked_root(archive)
        with ZipFile(archive) as source:
            cls.metadata = ET.fromstring(source.read("vi.xml"))

    def setUp(self):
        self.root = deepcopy(self.original)
        self.meta = deepcopy(self.metadata)
        self.frame = unique(self.root, "sequence", "359").find("diagramList")[4]
        self.loop = unique(self.root, "forLoop", "1176")

    def reject(self, message):
        with self.assertRaisesRegex(AssertionError, message):
            validate_cleanup_tree(self.root, self.meta)

    def test_saved_source_passes(self):
        self.assertEqual(len(validate_cleanup_tree(self.root, self.meta)), 4)

    def test_changed_fixed_uri_rejected(self):
        value = self.frame.find("nodeList/*/termList/*[@uid='18438']/dco/ConstValue")
        value.text = value.text.replace(
            b"10.20.30.2".hex().upper(), b"10.20.30.3".hex().upper(), 1
        )
        self.reject("fixed URI reference array")

    def test_truncated_uri_array_rejected(self):
        value = self.frame.find("nodeList/*/termList/*[@uid='18438']/dco/ConstValue")
        value.text = value.text[:-4]
        self.reject("URI bytes truncated")

    def test_dynamic_reference_input_rejected(self):
        self.frame.find("signalList/*/termList/*[@uid='18438']").set("uid", "62410")
        self.reject("cleanup frame wire set")

    def test_changed_autoindex_rejected(self):
        self.loop.find("termList/*[@uid='1772']/dco/TunnelType").text = "00"
        self.reject("auto-index tunnel")

    def test_initialized_error_register_rejected(self):
        signal = ET.SubElement(
            self.frame.find("signalList"), "SL__arrayElement", {"class": "signal"}
        )
        terms = ET.SubElement(signal, "termList")
        ET.SubElement(terms, "SL__arrayElement", {"uid": "13250"})
        ET.SubElement(terms, "SL__arrayElement", {"uid": "2051"})
        self.reject("cleanup frame wire set")

    def test_shift_register_pair_change_rejected(self):
        self.loop.find("termList/*[@uid='2051']/dco/rsrDCO").set("uid", "999")
        self.reject("shift-register pair")

    def test_error_accumulation_wire_change_rejected(self):
        self.loop.find("diagramList/*/signalList/*/termList/*[@uid='2050']").set(
            "uid", "2468"
        )
        self.reject("cleanup For body wire set")

    def test_extra_daq_cleanup_rejected(self):
        ET.SubElement(
            self.frame.find("zPlaneList"),
            "SL__arrayElement",
            {"class": "iUse", "uid": "999"},
        )
        self.reject("cleanup operations")

    def test_connection_close_primitive_change_rejected(self):
        unique(self.root, "prim", "536").find("primResID").text = "1922"
        self.reject("connection-close primitive")

    def test_stop_true_rejected(self):
        self.frame.find(
            "nodeList/*/termList/*[@uid='13250']/dco/ConstValue"
        ).text = "01"
        self.reject("stop reset is not False")

    def test_stop_local_change_rejected(self):
        unique(self.root, "gRef", "12978").find("termList/*/dco/paramIdx").text = "46"
        self.reject("stop local or write direction")

    def test_tpg_session_bank_change_rejected(self):
        unique(self.root, "gRef", "61778").find("termList/*/dco/paramIdx").text = "52"
        self.reject("TPG session bank")

    def test_tpg_connector_slot_change_rejected(self):
        unique(self.root, "iUse", "61121").find(
            "termList/*[@uid='61161']/dco/paramIdx"
        ).text = "8"
        self.reject("connector slot")

    def test_tpg_error_handler_source_change_rejected(self):
        self.frame.find("signalList/*/termList/*[@uid='61128']").set("uid", "66492")
        self.reject("cleanup frame wire set")

    def test_tpg_qualified_dependency_change_rejected(self):
        link = next(
            n
            for n in self.meta.findall(".//IUVI")
            if [s.text for s in n.findall("LinkSaveQualName/String")]
            == ["TPG 300.lvlib", "Close.vi"]
        )
        link.find("LinkSavePathRef/String[3]").text = "chr62000"
        self.reject("qualified dependency")

    def test_psp_handler_identity_change_rejected(self):
        unique(self.root, "iUse", "88").find(
            "label/textRec/text"
        ).text = '"Clear Errors.vi"'
        self.reject("error-handler identity/connector")

    def test_psp_handler_mode_slot_change_rejected(self):
        unique(self.root, "iUse", "88").find(
            "termList/*[@uid='2222']/dco/paramIdx"
        ).text = "9"
        self.reject("error-handler identity/connector")

    def test_handler_output_direction_change_rejected(self):
        unique(self.root, "iUse", "67965").find(
            "termList/*[@uid='67984']/dco/objFlags"
        ).text = "512"
        self.reject("error-handler identity/connector")

    def test_handler_output_cannot_reset_register(self):
        self.frame.find("signalList/*/termList/*[@uid='2048']").set("uid", "2198")
        self.reject("cleanup frame wire set")

    def test_explicit_handler_mode_wire_rejected(self):
        signal = ET.SubElement(
            self.frame.find("signalList"), "SL__arrayElement", {"class": "signal"}
        )
        terms = ET.SubElement(signal, "termList")
        ET.SubElement(terms, "SL__arrayElement", {"uid": "13250"})
        ET.SubElement(terms, "SL__arrayElement", {"uid": "2222"})
        self.reject("cleanup frame wire set")

    def test_psp_input_direction_change_rejected(self):
        unique(self.root, "prim", "536").find(
            "termList/*[@uid='1626']/dco/objFlags"
        ).text = "1"
        self.reject("PSP close input/output")

    def test_inert_cleanup_tags_and_branches_match_source(self):
        from DeviceServers.control.elyse_acq.vi_simulation.final_cleanup import (
            FIXED_PSP_TAGS,
            PSP_HANDLER,
            TPG_BRANCHES,
        )
        from validate_acq_final_cleanup import constant, tag_array

        self.assertEqual(
            tuple(tag_array(constant(self.frame, "18438"))), FIXED_PSP_TAGS
        )
        self.assertEqual(PSP_HANDLER, "88")
        self.assertEqual(TPG_BRANCHES, {51: ("61121", "68680"), 52: ("66474", "67965")})

    def test_outer_final_assignment_map_matches_saved_literals_and_banks(self):
        from DeviceServers.control.elyse_acq.vi_simulation.outer_stop_schedule import (
            FINAL_FRAME_WRITES,
        )
        from validate_acq_final_cleanup import constant

        phase = unique(self.root, "diag", "64826")
        for uid, port, literal, bank, value in (
            ("18163", "29020", "42334", 46, True),
            ("43536", "43559", "46100", 47, False),
        ):
            with self.subTest(node=uid):
                node = unique(self.root, "gRef", uid)
                self.assertIn(node, phase.find("zPlaneList"))
                self.assertEqual(node.findtext("termList/*/dco/paramIdx"), str(bank))
                self.assertEqual(node.findtext("termList/*/objFlags"), "36864")
                self.assertEqual(constant(phase, literal), "01" if value else "0000")
                self.assertIn(
                    frozenset((literal, port)),
                    {
                        frozenset(t.get("uid") for t in s.findall("termList/*"))
                        for s in phase.findall("signalList/*")
                    },
                )
                self.assertEqual(FINAL_FRAME_WRITES[uid], (bank, value))


class TPGCloseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_tpg_roots(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/TPG300_Close_XML_sha308f.zip"
        )

    def setUp(self):
        self.roots = deepcopy(self.original)

    def reject(self, message):
        with self.assertRaisesRegex(AssertionError, message):
            validate_tpg_trees(self.roots)

    def test_saved_source_passes(self):
        self.assertEqual(len(validate_tpg_trees(self.roots)), 1)

    def test_wrong_visa_primitive_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "prim", "104").find("primIndex").text = "258"
        self.reject("VISA Close primitive")

    def test_error_input_disconnected_rejected(self):
        self.roots["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='111']").set(
            "uid", "116"
        )
        self.reject("TPG Close wire set")

    def test_error_output_disconnected_rejected(self):
        self.roots["vi_BDHb.xml"].find("root/signalList/*/termList/*[@uid='109']").set(
            "uid", "111"
        )
        self.reject("TPG Close wire set")

    def test_connector_swap_rejected(self):
        self.roots["vi_FPHb.xml"].find(
            ".//conPane/cons/*[@index='11']/ConnectionDCO"
        ).set("uid", "3")
        self.reject("connector mapping")

    def test_public_terminal_identity_change_rejected(self):
        unique(self.roots["vi_BDHb.xml"], "fPTerm", "116").find("dco").set("uid", "3")
        self.reject("public terminal association")

    def test_extra_serial_command_rejected(self):
        ET.SubElement(
            self.roots["vi_BDHb.xml"].find("root/zPlaneList"),
            "SL__arrayElement",
            {"class": "iUse", "uid": "999"},
        )
        self.reject("body operations")


if __name__ == "__main__":
    unittest.main()
