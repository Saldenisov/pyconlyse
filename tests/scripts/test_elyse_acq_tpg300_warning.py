"""Immutable helper graph and discriminating error-code mutations."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_tpg300_warning import checked_warning, unique, validate_warning


class WarningSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_warning(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/TPG300_warning_XML_20261002.zip"
        )

    def test_all_source_facets_pass(self):
        self.assertIn("seven nets", validate_warning(self.roots))

    def test_each_diagram_net_mutation_rejected(self):
        for uid in ("84", "108", "116"):
            roots = deepcopy(self.roots)
            unique(roots["vi_BDHb.xml"], "diag", uid).find(
                "signalList/*/termList/*"
            ).set("uid", "999999")
            with self.assertRaises(AssertionError):
                validate_warning(roots)

    def test_error_code_field_and_case_polarity_sensitive(self):
        roots = deepcopy(self.roots)
        unique(roots["vi_BDHb.xml"], "nMux", "153").find(
            "termList/*[@uid='157']/dco/i"
        ).text = "0"
        with self.assertRaises(AssertionError):
            validate_warning(roots)
        roots = deepcopy(self.roots)
        unique(roots["vi_BDHb.xml"], "select", "89").find(
            "SelectRangeArray32/*/diagramIdx"
        ).text = "1"
        with self.assertRaises(AssertionError):
            validate_warning(roots)

    def test_warning_code_literal_sensitive(self):
        roots = deepcopy(self.roots)
        next(
            n
            for n in roots["vi_BDHb.xml"].iter()
            if n.get("uid") == "161" and n.find("ConstValue") is not None
        ).find("ConstValue").text = "00000000"
        with self.assertRaises(AssertionError):
            validate_warning(roots)


if __name__ == "__main__":
    unittest.main()
