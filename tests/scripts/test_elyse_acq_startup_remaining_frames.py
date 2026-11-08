"""Reject source mutations in both independently checked startup frames."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

import validate_acq_startup_io as io
import validate_acq_startup_postinit as post
from validate_acq_modulator_start_event_guards import unique
from validate_acq_runtime_io_frame import checked_trees, heap_type


class RemainingStartupFrames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd, cls.main = checked_trees(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_both_original_graphs_pass(self):
        self.assertIn("32 nets, 33 operations", io.validate_trees(self.bd, self.main))
        self.assertIn("31 operations, 17 nets", post.validate_trees(self.bd, self.main))

    def test_both_frame_orders_operations_and_nets_reject_mutation(self):
        for module, uid in ((io, "25990"), (post, "33052")):
            for path in ("zPlaneList/*", "signalList/*/termList/*"):
                bd = deepcopy(self.bd)
                unique(bd, "diag", uid).find(path).set("uid", "999999")
                with self.assertRaises(AssertionError):
                    module.validate_trees(bd, self.main)
            bd = deepcopy(self.bd)
            unique(bd, "diag", uid).set("uid", "999999")
            with self.assertRaises(AssertionError):
                module.validate_trees(bd, self.main)

    def test_each_initial_conversion_type_and_local_direction_rejects_mutation(self):
        for row in io.CONVERSIONS:
            bd = deepcopy(self.bd)
            unique(bd, "prim", row[0]).find(
                "termList/*/dco/typeDesc"
            ).text = "TypeID(1)"
            with self.assertRaises(AssertionError):
                io.validate_trees(bd, self.main)
        for module in (io, post):
            bd = deepcopy(self.bd)
            unique(bd, "gRef", module.LOCALS[0][0]).find(
                "termList/*/dco/objFlags"
            ).text = "0"
            with self.assertRaises(AssertionError):
                module.validate_trees(bd, self.main)

    def test_each_postinit_literal_and_ui_binding_rejects_mutation(self):
        for literal in post.LITERALS:
            bd = deepcopy(self.bd)
            unique(bd, "diag", "33052").find(
                f"nodeList/*/termList/*[@uid='{literal}']/dco/ConstValue"
            ).text = "FF"
            with self.assertRaises(AssertionError):
                post.validate_trees(bd, self.main)
        for uid, *_ in post.PROPERTIES:
            bd = deepcopy(self.bd)
            unique(bd, "propNode", uid).find("ddo").set("uid", "999999")
            with self.assertRaises(AssertionError):
                post.validate_trees(bd, self.main)

    def test_disabled_enum_meaning_and_tpg_callee_reject_mutation(self):
        main = deepcopy(self.main)
        descriptor, _ = heap_type(main, 2578)
        descriptor.find("EnumLabel").text = "Other"
        with self.assertRaises(AssertionError):
            post.validate_trees(self.bd, main)
        bd = deepcopy(self.bd)
        unique(bd, "iUse", "126853").find("termList/*").set("uid", "999999")
        with self.assertRaises(AssertionError):
            post.validate_trees(bd, self.main)


if __name__ == "__main__":
    unittest.main()
