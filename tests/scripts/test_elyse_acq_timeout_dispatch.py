"""Reject mutations in every explicit DPS arm and counter frame boundary."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
from validate_acq_timeout_dispatch import (
    DISPATCH,
    checked_vam,
    unique,
    validate_dispatch,
)


class TimeoutDispatchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def rejects(self, root):
        with self.assertRaises(AssertionError):
            validate_dispatch(root, self.meta)

    def test_original_passes(self):
        self.assertIn("31 diagrams / 60 nets", validate_dispatch(self.root, self.meta))

    def test_each_property_target_is_pinned(self):
        for _, prop, *_ in DISPATCH:
            with self.subTest(prop=prop):
                root = deepcopy(self.root)
                unique(root, "propNode", prop).find("ddo").set("uid", "999999")
                self.rejects(root)

    def test_each_property_arm_literal_is_pinned(self):
        for diag, _, _, literal, *_ in DISPATCH:
            with self.subTest(diag=diag):
                root = deepcopy(self.root)
                unique(root, "diag", diag).find(
                    f"nodeList/*/termList/*[@uid='{literal}']/dco/ConstValue"
                ).text = "0000"
                self.rejects(root)

    def test_numeric_default_not_fabricated(self):
        root = deepcopy(self.root)
        ET.SubElement(unique(root, "select", "8105"), "SelectDefaultCase").text = "00"
        self.rejects(root)

    def test_extra_wire_and_shifted_tunnel_rejected(self):
        root = deepcopy(self.root)
        unique(root, "diag", "23641").find("signalList/*/termList/*").set(
            "uid", "999999"
        )
        self.rejects(root)
        root = deepcopy(self.root)
        unique(root, "sequence", "23633").find("termList/*/dco/termList/*").set(
            "uid", "999999"
        )
        self.rejects(root)

    def test_fractional_guard_not_replaced_by_integer_range(self):
        root = deepcopy(self.root)
        unique(root, "prim", "21098").find("primResID").text = "1110"
        self.rejects(root)

    def test_reset_and_psp_boundary_are_not_error_gated(self):
        for diag in ("22979", "1507"):
            root = deepcopy(self.root)
            ET.SubElement(
                unique(root, "diag", diag).find("zPlaneList"),
                "SL__arrayElement",
                {"class": "select", "uid": "999999"},
            )
            self.rejects(root)

    def test_orphan_target_cannot_acquire_invented_handler(self):
        root = deepcopy(self.root)
        specs = unique(root, "eventStruct", "43").find("EventNodeEvents")
        specs[1].find("ddoUID").text = "66459"
        self.rejects(root)


if __name__ == "__main__":
    unittest.main()
