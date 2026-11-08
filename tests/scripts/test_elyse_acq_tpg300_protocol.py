"""Source guard mutations, independent of byte-loop golden expectations."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_tpg300_protocol import (
    CASES,
    CONSTANTS,
    NETS,
    PRIMITIVES,
    checked_roots,
    unique,
    validate_protocol,
)


class ProtocolSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_roots(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip"
        )["TPG300-Driver Core"]

    def changed(self):
        return deepcopy(self.roots)

    def rejected(self, roots):
        with self.assertRaises(AssertionError):
            validate_protocol(roots)

    def test_all_thirty_saved_diagrams_have_fixed_direct_nets(self):
        self.assertIn("27 additional diagrams", validate_protocol(self.roots))

    def test_each_nonempty_diagram_net_is_sensitive(self):
        for uid in NETS:
            if not NETS[uid]:
                continue
            with self.subTest(diagram=uid):
                roots = self.changed()
                unique(roots["vi_BDHb.xml"], "diag", uid).find(
                    "signalList/*/termList/*"
                ).set("uid", "999999")
                self.rejected(roots)

    def test_empty_cases_reject_added_operation(self):
        for uid in ("497", "1280"):
            roots = self.changed()
            target = unique(roots["vi_BDHb.xml"], "diag", uid).find("zPlaneList")
            target.append(deepcopy(unique(roots["vi_BDHb.xml"], "prim", "514")))
            self.rejected(roots)

    def test_all_case_polarities_and_tunnel_identities_are_sensitive(self):
        for uid in CASES:
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "select", uid).find(
                "SelectRangeArray32/*/diagramIdx"
            ).text = "1"
            self.rejected(roots)
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "select", uid).find(
                "termList/*/dco/termList/*"
            ).set("uid", "999999")
            self.rejected(roots)

    def test_every_literal_and_primitive_resource_is_sensitive(self):
        for uid in CONSTANTS:
            roots = self.changed()
            node = next(
                n
                for n in roots["vi_BDHb.xml"].iter()
                if n.get("uid") == uid and n.find("ConstValue") is not None
            )
            node.find("ConstValue").text = "DEADBEEF"
            self.rejected(roots)
        for uid in PRIMITIVES:
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "prim", uid).find("primResID").text = "0"
            self.rejected(roots)

    def test_ack_after_output_and_timeout_operand_slot_are_sensitive(self):
        for uid, port in (("1856", "1873"), ("400", "408"), ("1186", "1194")):
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "prim", uid).find(
                f"termList/*[@uid='{port}']/dco/parmIndex"
            ).text = "0"
            self.rejected(roots)

    def test_continue_polarity_and_ordinary_errors_are_sensitive(self):
        for uid, port in (("2041", "5002"), ("2059", "5130")):
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "whileLoop", uid).find(
                "loopTestDCO/objFlags"
            ).text = "65537"
            self.rejected(roots)
            roots = self.changed()
            unique(roots["vi_BDHb.xml"], "whileLoop", uid).find(
                f"termList/*[@uid='{port}']/dco"
            ).set("class", "lSR")
            self.rejected(roots)

    def test_property_and_saved_tokens_are_sensitive(self):
        roots = self.changed()
        unique(roots["vi_BDHb.xml"], "propNode", "3353").find(
            "termList/*/dco/propList/*/PropItemCode"
        ).text = "0"
        self.rejected(roots)
        for uid in ("11", "18", "46", "32"):
            roots = self.changed()
            unique(roots["vi_FPHb.xml"], "fPDCO", uid).find(
                "DefaultData"
            ).text = '"changed"'
            self.rejected(roots)


if __name__ == "__main__":
    unittest.main()
