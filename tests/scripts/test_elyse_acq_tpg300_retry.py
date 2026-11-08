"""Outer retry proof only; no promotion of the inner protocol to coverage."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from validate_acq_tpg300_retry import NETS, checked_roots, unique, validate_core


class RetrySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_roots(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/TPG300_startup_XML_20261002.zip"
        )["TPG300-Driver Core"]

    def test_original_outer_facets_pass(self):
        self.assertIn("25 nets", validate_core(self.roots))

    def test_each_outer_net_mutation_rejected(self):
        for uid in NETS:
            roots = deepcopy(self.roots)
            unique(roots["vi_BDHb.xml"], "diag", uid).find(
                "signalList/*/termList/*"
            ).set("uid", "999999")
            with self.assertRaises(AssertionError):
                validate_core(roots)

    def test_loop_polarity_and_status_field_mutations_rejected(self):
        roots = deepcopy(self.roots)
        unique(roots["vi_BDHb.xml"], "whileLoop", "2067").find(
            "loopTestDCO/objFlags"
        ).text = "65537"
        with self.assertRaises(AssertionError):
            validate_core(roots)
        roots = deepcopy(self.roots)
        parent = unique(roots["vi_BDHb.xml"], "nMux", "798").find(
            "termList/*[@uid='2473']/dco"
        )
        ET.SubElement(parent, "i").text = "1"
        with self.assertRaises(AssertionError):
            validate_core(roots)

    def test_phase_two_provenance_and_retry_default_mutations_rejected(self):
        roots = deepcopy(self.roots)
        unique(roots["vi_BDHb.xml"], "sLoc", "1521").find("diagDefined").text = "01"
        with self.assertRaises(AssertionError):
            validate_core(roots)
        roots = deepcopy(self.roots)
        unique(roots["vi_FPHb.xml"], "fPDCO", "39").find(
            "DefaultData"
        ).text = '"changed"'
        with self.assertRaises(AssertionError):
            validate_core(roots)


if __name__ == "__main__":
    unittest.main()
