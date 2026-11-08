"""Distinguish source-bound UI enabling from stop-value writes."""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from validate_acq_modulator_start_event_guards import unique
from validate_acq_stop_ui_bindings import (
    CONTROLS,
    checked_trees,
    validate_trees,
)


class StopUiBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd, cls.fp, cls.meta = checked_trees()

    def test_seven_controls_ten_properties_do_not_prove_initial_or_boolean_values(self):
        result = validate_trees(self.bd, self.fp, self.meta)
        self.assertEqual(result["front_panel_controls"], 7)
        self.assertEqual(result["direct_disabled_properties"], 10)
        self.assertEqual(result["direct_value_property_writers"], ())
        self.assertFalse(result["initial_values_proven"])
        self.assertFalse(result["indirect_writers_excluded"])

    def test_every_control_label_binding_is_checked(self):
        for control, *_ in CONTROLS:
            label = unique(self.fp, "fPDCO", control).find(
                "ddo/partsList/*[@class='label']/textRec/text"
            )
            before = label.text
            label.text = '"Wrong stop control"'
            try:
                with self.subTest(control=control), self.assertRaises(AssertionError):
                    validate_trees(self.bd, self.fp, self.meta)
            finally:
                label.text = before

    def test_changed_property_target_or_value_semantics_is_rejected(self):
        prop = unique(self.bd, "propNode", "120269")
        target = prop.find("ddo")
        before = target.get("uid")
        target.set("uid", "1627")
        try:
            with self.assertRaises(AssertionError):
                validate_trees(self.bd, self.fp, self.meta)
        finally:
            target.set("uid", before)
        item = prop.find(".//PropItemCode")
        before = item.text
        item.text = "999"
        try:
            with self.assertRaises(AssertionError):
                validate_trees(self.bd, self.fp, self.meta)
        finally:
            item.text = before

    def test_added_direct_boolean_property_writer_cannot_hide(self):
        root = self.bd.find(".//*[@class='diag'][@uid='3']/zPlaneList")
        node = ET.SubElement(
            root, "SL__arrayElement", {"class": "propNode", "uid": "extra"}
        )
        ET.SubElement(node, "ddo", {"uid": "45845"})
        try:
            with self.assertRaises(AssertionError):
                validate_trees(self.bd, self.fp, self.meta)
        finally:
            root.remove(node)


if __name__ == "__main__":
    unittest.main()
