"""Whole-root stop memory census and source/model drift rejection."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from validate_acq_modulator_start_event_guards import unique
from validate_acq_stop_state_memory import SITES, STOP_RESETS, validate_memory
from validate_acq_vam_status import checked_vam

REPO = Path(__file__).resolve().parents[2]


class StopStateMemorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPO / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_all20_references_and11_literal_writers_are_checked(self):
        result = validate_memory(self.root, self.meta)
        self.assertEqual(result["stop_local_references"], 20)
        self.assertEqual(result["literal_writers"], 11)
        self.assertEqual(result["init_gref_resets"], ((45, False), (46, False)))
        for key in (
            "init_gref_reset_30_or_47",
            "loaded_initial_values_proven",
            "indirect_writers_excluded",
        ):
            self.assertFalse(result[key])

    def test_every_reference_bank_binding_is_verified(self):
        for node, *_ in SITES:
            item = unique(self.root, "gRef", node).find("termList/*/dco/paramIdx")
            before = item.text
            item.text = "30" if before != "30" else "47"
            try:
                with self.subTest(node=node), self.assertRaises(AssertionError):
                    validate_memory(self.root, self.meta)
            finally:
                item.text = before

    def test_census_rejects_an_added_initializer_stop_reset(self):
        initializer = unique(self.root, "diag", "33052").find("zPlaneList")
        writer = unique(self.root, "gRef", "12978")
        added = copy.deepcopy(writer)
        added.set("uid", "extra_initializer_stop_reset")
        initializer.append(added)
        try:
            with self.assertRaises(AssertionError):
                validate_memory(self.root, self.meta)
        finally:
            initializer.remove(added)

    def test_constant_polarity_and_runtime_condition_polarity_mutations_fail(self):
        for item in (
            unique(self.root, "diag", "33052").find(
                "nodeList/*/termList/*[@uid='18008']/dco/ConstValue"
            ),
            unique(self.root, "lTst", "47497").find("objFlags"),
        ):
            before = item.text
            item.text = "01" if item.tag == "ConstValue" else "65536"
            try:
                with self.assertRaises(AssertionError):
                    validate_memory(self.root, self.meta)
            finally:
                item.text = before

    def test_python_reset_plan_cannot_add_unobserved_startup_flags(self):
        with patch.dict(
            STOP_RESETS, {"post_init": ((30, False), (45, False), (46, False))}
        ):
            with self.assertRaises(AssertionError):
                validate_memory(self.root, self.meta)


if __name__ == "__main__":
    unittest.main()
