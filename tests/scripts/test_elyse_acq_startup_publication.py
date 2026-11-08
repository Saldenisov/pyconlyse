"""Saved startup wire/literal/type proof and discriminating mutations."""

import sys
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation import startup_publication as model
from validate_acq_startup_publication import (
    COMMAND_PUBLICATIONS,
    COMMANDS,
    STATUS_PUBLICATIONS,
    checked_trees,
    heap_type,
    unique,
    validate_trees,
)


class StartupSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd, cls.main = checked_trees(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_graph_and_model_literals_agree(self):
        self.assertIn("40 nets, 53 operations", validate_trees(self.bd, self.main))
        self.assertEqual(model.STARTUP_COMMANDS, tuple((r[4], r[6]) for r in COMMANDS))
        self.assertEqual(
            model.COMMAND_PUBLICATIONS,
            tuple((r[0], r[2], r[5]) for r in COMMAND_PUBLICATIONS),
        )
        self.assertEqual(
            model.STATUS_PUBLICATIONS,
            tuple((r[0], r[2], r[5]) for r in STATUS_PUBLICATIONS),
        )
        self.assertEqual(sum(len(r[6]) for r in COMMANDS), 152)

    def test_every_command_literal_and_heap_mutation_rejected(self):
        for literal, heap, *_ in COMMANDS:
            for target, value in (("ConstValue", "00"), ("typeDesc", "TypeID(1)")):
                bd = deepcopy(self.bd)
                unique(bd, "diag", "14803").find(
                    f"nodeList/*/termList/*[@uid='{literal}']/dco/{target}"
                ).text = value
                with self.assertRaises(AssertionError):
                    validate_trees(bd, self.main)
            main = deepcopy(self.main)
            descriptor, _ = heap_type(main, heap)
            descriptor.remove(descriptor.find("TypeDesc"))
            with self.assertRaises(AssertionError):
                validate_trees(self.bd, main)

    def test_all_three_frame_operations_and_net_mutations_rejected(self):
        for uid in ("14803", "24611", "17881"):
            for target in ("zPlaneList/*", "signalList/*/termList/*"):
                bd = deepcopy(self.bd)
                unique(bd, "diag", uid).find(target).set("uid", "999999")
                with self.assertRaises(AssertionError):
                    validate_trees(bd, self.main)

    def test_each_uri_and_psp_direction_mutation_rejected(self):
        for frame, rows in (
            ("24611", COMMAND_PUBLICATIONS),
            ("17881", STATUS_PUBLICATIONS),
        ):
            for row in rows:
                bd = deepcopy(self.bd)
                unique(bd, "diag", frame).find(
                    f"nodeList/*/termList/*[@uid='{row[4]}']/dco/ConstValue"
                ).text = "00000000"
                with self.assertRaises(AssertionError):
                    validate_trees(bd, self.main)
                bd = deepcopy(self.bd)
                unique(bd, "sharedVariableDynamicWrite", row[0]).find(
                    "termList/*/dco/objFlags"
                ).text = "512"
                with self.assertRaises(AssertionError):
                    validate_trees(bd, self.main)

    def test_raw_error_cannot_be_replaced_by_fallback_error(self):
        for uid, replacement in (("133", "2112"), ("7580", "7590")):
            bd = deepcopy(self.bd)
            unique(bd, "diag", uid).find("signalList/*/termList/*").set(
                "uid", replacement
            )
            with self.assertRaises(AssertionError):
                validate_trees(bd, self.main)
        bd = deepcopy(self.bd)
        unique(bd, "sLoc", "25655").find("diagDefined").text = "05"
        with self.assertRaises(AssertionError):
            validate_trees(bd, self.main)

    def test_status_field_not_primitive_and_type_mutations_rejected(self):
        for uid, target, value in (
            ("31306", "termList/*[@uid='31316']/dco/i", "1"),
            ("28019", "termList/*[@uid='28766']/dco/i", "1"),
            ("24445", "primResID", "1065"),
            ("16847", "primIndex", "29"),
        ):
            bd = deepcopy(self.bd)
            node = next(n for n in bd.iter() if n.get("uid") == uid and n.get("class"))
            leaf = node.find(target)
            if leaf is None:
                parent, tag = target.rsplit("/", 1)
                leaf = ET.SubElement(node.find(parent), tag)
            leaf.text = value
            with self.assertRaises(AssertionError):
                validate_trees(bd, self.main)
        for heap in (2595, 2597, 2604, 2615, 2616):
            main = deepcopy(self.main)
            descriptor, _ = heap_type(main, heap)
            descriptor.remove(descriptor.find("TypeDesc"))
            with self.assertRaises(AssertionError):
                validate_trees(self.bd, main)

    def test_stage_order_and_error_tunnel_mutations_rejected(self):
        for sequence in ("201", "24603"):
            bd = deepcopy(self.bd)
            frames = unique(bd, "sequence", sequence).find("diagramList")
            first = frames[0]
            frames.remove(first)
            frames.insert(1, first)
            with self.assertRaises(AssertionError):
                validate_trees(bd, self.main)
        bd = deepcopy(self.bd)
        unique(bd, "sequence", "24603").find("termList/*/dco/objFlags").text = "0"
        with self.assertRaises(AssertionError):
            validate_trees(bd, self.main)


if __name__ == "__main__":
    unittest.main()
