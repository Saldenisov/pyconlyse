"""Inert source and negative-mutation checks of the EPS admission trace."""

import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import trace_acq_stage_admission as trace


class AcqStageAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = trace.checked_vam(trace.ACQ)
        cls.fp = trace.checked_fp()
        cls.catalog = trace.build_catalog()

    def test_all_39_eps_read_consumers_are_classified(self):
        result = trace.inspect_eps(self.root, self.meta)
        self.assertEqual(result["total_local_references"], 66)
        self.assertEqual(result["reader_categories"]["preserve_other_fields_in_literal_bundle"], 25)
        self.assertEqual(result["reader_categories"]["sharedVariableDynamicWrite"], 12)
        self.assertFalse(result["direct_eps_predicate_read_found"])
        self.assertEqual(result["direct_fieldwise_writers_of_start_ed_13_19_31"], [])

    def test_all_three_request_completion_and_dio_paths(self):
        result = trace.stage_paths(self.catalog, trace.bank_labels(self.root, self.meta, 44))
        self.assertEqual([r["eps_request"] for r in result], [12, 18, 30])
        self.assertEqual([r["dps_request"] for r in result], [4, 6, 10])
        self.assertEqual([r["c4_assignments"][0][1] for r in result], [3, 5, 7])
        self.assertEqual([r["event"] for r in result], [12, 13, 15])
        self.assertEqual([r["focal_helper"] for r in result], [None, None, "1_Focales ON.vi"])

    def test_nested_eps_controls_match_dispatch_and_registered_events(self):
        result = trace.inspect_targets(self.root, self.fp)
        self.assertEqual(result["public_connector"], -1)
        self.assertEqual(result["static_property_targets"], 24)

    def test_eps_cannot_gain_a_hidden_reader(self):
        root = copy.deepcopy(self.root)
        root.append(ET.fromstring('<n class="gRef" uid="HIDDEN"><termList>'
                                 '<t class="term" uid="HIDDEN_PORT"><dco>'
                                 '<paramIdx>44</paramIdx><objFlags>1</objFlags>'
                                 '</dco></t></termList></n>'))
        with self.assertRaisesRegex(AssertionError, "EPS .*census"):
            trace.inspect_eps(root, self.meta)

    def test_eps_cannot_gain_a_predicate_fanout(self):
        root = copy.deepcopy(self.root)
        signal = trace.unique(root, "signal", "38589")
        signal.find("termList").append(ET.Element("port", uid="UNREVIEWED_GUARD"))
        with self.assertRaisesRegex(AssertionError, "another consumer"):
            trace.inspect_eps(root, self.meta)

    def test_bundle_read_cannot_be_mistaken_for_unbundle(self):
        root = copy.deepcopy(self.root)
        trace.unique(root, "nMux", "38527").find("objFlags").text = "327680"
        with self.assertRaisesRegex(AssertionError, "Bundle base input"):
            trace.inspect_eps(root, self.meta)

    def test_new_direct_ed_writer_is_rejected(self):
        root = copy.deepcopy(self.root)
        mux = trace.unique(root, "nMux", "38527")
        leaf = next(t for t in mux.findall("termList/*") if t.findtext("dco/i") == "14")
        leaf.find("dco/i").text = "13"
        with self.assertRaisesRegex(AssertionError, "ED flags"):
            trace.inspect_eps(root, self.meta)

    def test_unwired_main_eps_terminal_cannot_gain_predicate(self):
        root = copy.deepcopy(self.root)
        root.append(ET.fromstring('<s class="signal" uid="EXTRA"><termList>'
                                 '<p uid="66774"/><p uid="NEW_GUARD"/></termList></s>'))
        with self.assertRaisesRegex(AssertionError, "front-panel terminal"):
            trace.inspect_eps(root, self.meta)

    def test_request_target_field_cannot_be_swapped(self):
        fp = copy.deepcopy(self.fp)
        items = trace.unique(fp, "fPDCO", "66772").findall("ddo/ddoList/*")
        items[12].set("uid", "66627")
        items[18].set("uid", "66579")
        with self.assertRaisesRegex(AssertionError, "expected EPS request field"):
            trace.inspect_targets(self.root, fp)

    def test_static_eps_property_cannot_become_a_read(self):
        root = copy.deepcopy(self.root)
        node = trace.unique(root, "propNode", "29098")
        dco = node.findall("termList/*")[4].find("dco")
        flags = dco.find("objFlags")
        if flags is None:
            flags = ET.SubElement(dco, "objFlags")
        flags.text = "1"
        with self.assertRaisesRegex(AssertionError, "read-side value"):
            trace.inspect_targets(root, self.fp)

    def test_software_ok_cannot_be_changed_to_ed(self):
        catalog = copy.deepcopy(self.catalog)
        for _, effect in trace.flatten_frames(catalog["procedures"]["chauffage.start"]["frames"]):
            if effect[:2] == ["write", 44]:
                next(pair for pair in effect[2] if pair[0] == 14)[0] = 13
        with self.assertRaisesRegex(AssertionError, "completion EPS assignments"):
            trace.stage_paths(catalog, trace.bank_labels(self.root, self.meta, 44))

    def test_saved_report_matches_full_source_proof_without_actuation(self):
        result = trace.build()
        self.assertEqual(json.loads(trace.OUTPUT.read_text("utf-8")), result)
        for key in ("screen_used", "hardware_commands_sent", "vi_run_or_saved",
                    "runtime_code_changed", "qualifies_hardware_start"):
            self.assertFalse(result[key])


if __name__ == "__main__":
    unittest.main()
