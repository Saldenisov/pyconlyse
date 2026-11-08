"""Copied vendor source identities and state-graph mutation checks."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_tpg300_startup import (
    INIT_NETS,
    checked_roots,
    heap_type,
    unique,
    validate_initializer,
    validate_serial,
)


class TpgSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_roots(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip"
        )

    def test_original_graphs_pass_without_claiming_core_protocol(self):
        self.assertIn(
            "nine diagrams, 85 nets", validate_initializer(self.roots["Initialize"])
        )
        self.assertIn(
            "three diagrams, 18 nets", validate_serial(self.roots["TPG300-Serial Init"])
        )

    def test_all_nine_initializer_nets_and_operation_censuses_reject_mutation(self):
        for uid in INIT_NETS:
            for path in ("signalList/*/termList/*", "zPlaneList/*"):
                roots = deepcopy(self.roots["Initialize"])
                unique(roots["vi_BDHb.xml"], "diag", uid).find(path).set(
                    "uid", "999999"
                )
                with self.assertRaises(AssertionError):
                    validate_initializer(roots)

    def test_select_polarity_tunnel_and_state_label_mutations_rejected(self):
        for uid, path in (
            ("308", "termList/*[@uid='326']/dco/parmIndex"),
            ("647", "termList/*/dco/termList/*"),
            ("818", "loopTestDCO/objFlags"),
        ):
            roots = deepcopy(self.roots["Initialize"])
            node = next(
                n for n in roots["vi_BDHb.xml"].iter() if n.get("uid") == uid and len(n)
            )
            leaf = node.find(path)
            if leaf is None:
                import xml.etree.ElementTree as ET

                leaf = ET.SubElement(node.find("termList/*/dco"), "parmIndex")
            if path.endswith("/*"):
                leaf.set("uid", "999999")
            else:
                leaf.text = "1" if uid == "308" else "65537"
            with self.assertRaises(AssertionError):
                validate_initializer(roots)
        roots = deepcopy(self.roots["Initialize"])
        heap_type(roots["vi.xml"], 216)[0].find("EnumLabel").text = "Other"
        with self.assertRaises(AssertionError):
            validate_initializer(roots)

    def test_serial_buffer_and_termination_literals_reject_mutation(self):
        for uid, path in (("171", "DefaultData"), ("251", "DefaultData")):
            roots = deepcopy(self.roots["TPG300-Serial Init"])
            unique(roots["vi_FPHb.xml"], "fPDCO", uid).find(path).text = '"changed"'
            with self.assertRaises(AssertionError):
                validate_serial(roots)
        roots = deepcopy(self.roots["TPG300-Serial Init"])
        unique(roots["vi_BDHb.xml"], "diag", "493").find(
            "nodeList/*/termList/*[@uid='1081']/dco/ConstValue"
        ).text = "0001"
        with self.assertRaises(AssertionError):
            validate_serial(roots)


if __name__ == "__main__":
    unittest.main()
