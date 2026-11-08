"""Source pins and mutations of parser, caller, locale and status wires."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_tpg300_pressure import (
    POINT_NETS,
    checked_export,
    checked_root,
    unique,
    validate_callers,
    validate_point,
    validate_pressure,
    validate_pressure_publication,
)


class PressureSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = REPOSITORY / "legacy/xp_acq_agent/data/source_exports"
        cls.pressure = checked_export(
            directory / "TPG300_pressure_XML_20261002.zip", "pressure"
        )
        cls.point = checked_export(directory / "TPG300_point_XML_20261002.zip", "point")
        cls.root = checked_root(directory / "0_ACQ_ELYSE_XML_sha6fe8.zip")

    def test_source_facets_pass(self):
        self.assertIn("16 nets", validate_pressure(self.pressure))
        self.assertIn("20 nets", validate_point(self.point))
        self.assertIn("14 nets", validate_callers(self.root))
        self.assertIn("four nets", validate_pressure_publication(self.root))

    def test_all_helper_diagram_net_mutations_rejected(self):
        for original, validator, uids in (
            (self.pressure, validate_pressure, ("86",)),
            (self.point, validate_point, POINT_NETS),
        ):
            for uid in uids:
                roots = deepcopy(original)
                unique(roots["vi_BDHb.xml"], "diag", uid).find(
                    "signalList/*/termList/*"
                ).set("uid", "999999")
                with self.assertRaises(AssertionError):
                    validator(roots)

    def test_point_selector_literal_and_loop_polarity_sensitive(self):
        for uid, field, value in (
            ("207", "SelectRangeArray32/*/diagramIdx", "1"),
            ("281", "loopTestDCO/objFlags", "65537"),
        ):
            roots = deepcopy(self.point)
            node = unique(
                roots["vi_BDHb.xml"], "select" if uid == "207" else "whileLoop", uid
            )
            node.find(field).text = value
            with self.assertRaises(AssertionError):
                validate_point(roots)
        roots = deepcopy(self.point)
        next(
            n
            for n in roots["vi_BDHb.xml"].iter()
            if n.get("uid") == "213" and n.find("ConstValue") is not None
        ).find("ConstValue").text = "000000012E"
        with self.assertRaises(AssertionError):
            validate_point(roots)

    def test_caller_status_substitution_and_sensor_literal_sensitive(self):
        root = deepcopy(self.root)
        unique(root, "diag", "48320").find("signalList/*/termList/*[@uid='46260']").set(
            "uid", "46257"
        )
        with self.assertRaises(AssertionError):
            validate_callers(root)
        root = deepcopy(self.root)
        next(
            n
            for n in root.iter()
            if n.get("uid") == "52679" and n.find("ConstValue") is not None
        ).find("ConstValue").text = "00000002"
        with self.assertRaises(AssertionError):
            validate_callers(root)

    def test_downstream_bank_reader_and_bundle_field_sensitive(self):
        root = deepcopy(self.root)
        unique(root, "gRef", "7630").find("termList/*/dco/paramIdx").text = "54"
        with self.assertRaises(AssertionError):
            validate_callers(root)
        root = deepcopy(self.root)
        unique(root, "nMux", "21214").find("termList/*[@uid='72069']/dco/i").text = "11"
        with self.assertRaises(AssertionError):
            validate_callers(root)

    def test_publication_case_wire_and_fault_assignment_sensitive(self):
        for uid in ("77141", "42989"):
            root = deepcopy(self.root)
            unique(root, "diag", uid).find("signalList/*/termList/*").set(
                "uid", "999999"
            )
            with self.assertRaises(AssertionError):
                validate_pressure_publication(root)
        root = deepcopy(self.root)
        unique(root, "gRef", "43027").find("termList/*/dco/paramIdx").text = "45"
        with self.assertRaises(AssertionError):
            validate_pressure_publication(root)


if __name__ == "__main__":
    unittest.main()
