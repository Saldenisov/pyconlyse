"""Focal whole-graph proofs, saved literal correspondence and mutations."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.focal_helpers import (
    NODES,
    STEPS,
    VALUES,
)
from validate_acq_focal_helpers import (
    OFF_BRANCHES,
    ON_BRANCHES,
    checked_roots,
    unique,
    validate_member,
)


class FocalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_roots(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports"
            / "ACQ_17_original_members_XML_20261001.zip"
        )

    def roots(self, enabled):
        return deepcopy(
            self.original["1_Focales " + ("ON" if enabled else "OFF") + ".vi"]
        )

    def test_original_graphs_and_model_node_order_match(self):
        for enabled in (True, False):
            self.assertIn(
                "three independent six-call",
                validate_member(self.roots(enabled), enabled=enabled),
            )
            rows = ON_BRANCHES if enabled else OFF_BRANCHES
            self.assertEqual(NODES[enabled], {r[0]: r[1] for r in rows})
        self.assertEqual(
            STEPS,
            (
                "Initialize",
                "Set Voltage",
                "Set Current Slew",
                "Set Current",
                "Set Output",
                "Close",
            ),
        )
        self.assertEqual(
            VALUES,
            {3: (70.0, 0.02, 15.1), 2: (80.0, 0.02, 20.9), 1: (80.0, 0.02, 13.73)},
        )

    def test_each_chain_wire_and_connected_literal_mutation_rejected(self):
        for enabled in (True, False):
            for row in ON_BRANCHES if enabled else OFF_BRANCHES:
                roots = self.roots(enabled)
                unique(roots["vi_BDHb.xml"], "iUse", row[1][-1]).find("termList/*").set(
                    "uid", "999999"
                )
                with self.assertRaisesRegex(AssertionError, "wire set"):
                    validate_member(roots, enabled=enabled)
                roots = self.roots(enabled)
                roots["vi_BDHb.xml"].find(
                    f"root/nodeList/*/termList/*[@uid='{row[4][2]}']/dco/ConstValue"
                ).text = "0000000000000000"
                with self.assertRaisesRegex(AssertionError, "voltage/slew/current"):
                    validate_member(roots, enabled=enabled)

    def test_off_output_and_reset_cannot_be_silently_changed(self):
        for index, value in ((5, "01"), (1, "0000")):
            roots = self.roots(False)
            term = OFF_BRANCHES[0][4][index]
            roots["vi_BDHb.xml"].find(
                f"root/nodeList/*/termList/*[@uid='{term}']/dco/ConstValue"
            ).text = value
            with self.assertRaisesRegex(AssertionError, "ID-query/reset/output"):
                validate_member(roots, enabled=False)

    def test_unwired_initialize_error_input_cannot_gain_an_edge(self):
        roots = self.roots(True)
        frame = roots["vi_BDHb.xml"].find("root")
        target = (
            unique(roots["vi_BDHb.xml"], "iUse", "738")
            .findall("termList/*")[8]
            .get("uid")
        )
        frame.find("signalList/*/termList/*").set("uid", target)
        with self.assertRaisesRegex(AssertionError, "wire set"):
            validate_member(roots, enabled=True)

    def test_merge_order_and_resource_default_checked(self):
        roots = self.roots(False)
        merge = unique(roots["vi_BDHb.xml"], "mergeErrors", "2758")
        merge.find("dcoList/*").set("uid", "2824")
        with self.assertRaisesRegex(AssertionError, "merge order"):
            validate_member(roots, enabled=False)
        roots = self.roots(True)
        unique(roots["vi_FPHb.xml"], "fPDCO", "561").find("DefaultData").text = "COM99"
        with self.assertRaisesRegex(AssertionError, "resource default"):
            validate_member(roots, enabled=True)

    def test_hidden_operation_and_public_error_input_rejected(self):
        roots = self.roots(True)
        extra = deepcopy(unique(roots["vi_BDHb.xml"], "iUse", "738"))
        extra.set("uid", "999999")
        roots["vi_BDHb.xml"].find("root/zPlaneList").append(extra)
        with self.assertRaisesRegex(AssertionError, "operations"):
            validate_member(roots, enabled=True)
        roots = self.roots(False)
        roots["vi.xml"].find("CPMp/Section/TypeDesc").set("Flags", "0x0100")
        with self.assertRaisesRegex(AssertionError, "connector"):
            validate_member(roots, enabled=False)


if __name__ == "__main__":
    unittest.main()
