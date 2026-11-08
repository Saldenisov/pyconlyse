"""Exact original graphs plus per-diagram net/node mutations and scalar gates."""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_controlled_stop import audit_fragment, qualify
from validate_acq_controlled_stop import validate_stop
from validate_acq_lifecycle_envelopes import DIAGRAMS, validate_envelopes
from validate_acq_modulator_start_event_guards import unique
from validate_acq_vam_status import checked_vam


class ControlledStopSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )
        cls.proof = validate_stop(cls.root, cls.meta)

    def test_all57_remaining_root_graphs_have_exact_direct_net_proofs(self):
        self.assertEqual(self.proof["diagrams"], 45)
        self.assertEqual(self.proof["nets"], 152)
        proof = validate_envelopes(self.root, self.meta)
        self.assertEqual(proof["diagrams"], 12)
        self.assertEqual(proof["nets"], 52)
        self.assertFalse(set(proof["diagram_uids"]) & set(self.proof["diagram_uids"]))

    def test_every_stop_graph_rejects_an_added_net_or_operation(self):
        for uid in self.proof["diagram_uids"]:
            frame = unique(self.root, "diag", uid)
            signals = frame.find("signalList")
            extra = ET.SubElement(
                signals,
                "SL__arrayElement",
                attrib={"class": "signal", "uid": "UNREVIEWED"},
            )
            ET.SubElement(extra, "termList")
            try:
                with self.subTest(diagram=uid), self.assertRaises(AssertionError):
                    validate_stop(self.root, self.meta)
            finally:
                signals.remove(extra)

    def test_every_lifecycle_envelope_rejects_unexplained_fanout(self):
        for uid in DIAGRAMS:
            frame = unique(self.root, "diag", uid)
            signals = frame.find("signalList")
            extra = ET.SubElement(
                signals,
                "SL__arrayElement",
                attrib={"class": "signal", "uid": "UNREVIEWED"},
            )
            ET.SubElement(extra, "termList")
            try:
                with self.subTest(diagram=uid), self.assertRaises(AssertionError):
                    validate_envelopes(self.root, self.meta)
            finally:
                signals.remove(extra)

    def test_ramp_operator_field_and_stop_polarity_mutations_fail(self):
        for target in (
            unique(self.root, "prim", "44754").find("primResID"),
            unique(self.root, "prim", "583").find("primResID"),
            unique(self.root, "nMux", "42188").find("termList/*[@uid='42198']/dco/i"),
            unique(self.root, "whileLoop", "18613").find("loopTestDCO/objFlags"),
        ):
            # Field0 is an omitted default tag; mutate by inserting it explicitly.
            if target is None:
                parent = unique(self.root, "nMux", "42188").find(
                    "termList/*[@uid='42198']/dco"
                )
                target = ET.SubElement(parent, "i")
                target.text = "1"
                try:
                    with self.assertRaises(AssertionError):
                        validate_stop(self.root, self.meta)
                finally:
                    parent.remove(target)
                continue
            before = target.text
            target.text = "0"
            try:
                with self.assertRaises(AssertionError):
                    validate_stop(self.root, self.meta)
            finally:
                target.text = before

    def test_ht_readback_is_not_changed_to_c1_or_another_field(self):
        field = unique(self.root, "nMux", "42777").find(
            "termList/*[@uid='48893']/dco/i"
        )
        before = field.text
        field.text = "6"
        try:
            with self.assertRaises(AssertionError):
                validate_envelopes(self.root, self.meta)
        finally:
            field.text = before

    def test_shared_lvkit_only_executes_pure_scalar_fragments(self):
        with patch(
            "socket.socket.connect", side_effect=AssertionError("network forbidden")
        ):
            receipt = qualify()
        self.assertEqual(receipt["scalar_fragments"], 4)
        self.assertEqual(receipt["scalar_cases"], 826)
        for key in (
            "whole_acquisition_qualified",
            "hardware_executed",
            "vi_executed",
            "deployable",
        ):
            self.assertFalse(receipt[key])

    def test_scalar_audit_rejects_external_access_unbound_names_and_input_write(self):
        for source in (
            "import socket\nresult = checked",
            "result = open('x')",
            "checked = 1.0\nresult = checked",
            "result = checked.__class__",
            "result = missing",
            "while True: pass",
            "result = checked * 2",
        ):
            with self.subTest(source=source), self.assertRaises(AssertionError):
                audit_fragment(source, ("checked",))


if __name__ == "__main__":
    unittest.main()
