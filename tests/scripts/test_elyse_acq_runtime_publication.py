"""Source proof and mutations for runtime publication/comparison/loop facets."""

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))
sys.path.insert(0, str(REPOSITORY))

from DeviceServers.control.elyse_acq.vi_simulation.runtime_publication import (
    PUBLICATIONS as MODEL,
)
from validate_acq_runtime_publication import (
    PUBLICATIONS,
    checked_root,
    unique,
    validate_tree,
)


class RuntimePublicationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = checked_root(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )

    def test_original_and_python_request_order(self):
        self.assertIn("8 ordered PSP", validate_tree(self.original))
        self.assertEqual(MODEL, tuple((r[0], r[2], r[5]) for r in PUBLICATIONS))

    def test_all_uri_mutations_rejected(self):
        for row in PUBLICATIONS:
            root = deepcopy(self.original)
            frame = unique(root, "diag", "7392")
            frame.find(
                f"nodeList/*/termList/*[@uid='{row[4]}']/dco/ConstValue"
            ).text = "00000000"
            with self.assertRaisesRegex(AssertionError, "destination literal"):
                validate_tree(root)

    def test_all_writer_port_mutations_rejected(self):
        for row in PUBLICATIONS:
            root = deepcopy(self.original)
            unique(root, "sharedVariableDynamicWrite", row[0]).find(
                "termList/*/dco/terminal_ID"
            ).text = "0A"
            with self.assertRaisesRegex(AssertionError, "writer ports/directions"):
                validate_tree(root)

    def test_chain_edge_and_local_identity_mutations_rejected(self):
        for uid in ("7392", "50030", "1619", "8619", "211"):
            root = deepcopy(self.original)
            unique(root, "diag", uid).find("signalList/*/termList/*").set(
                "uid", "999999"
            )
            with self.assertRaisesRegex(AssertionError, "wire set"):
                validate_tree(root)
        root = deepcopy(self.original)
        unique(root, "gRef", "50019").find("termList/*/dco/paramIdx").text = "30"
        with self.assertRaisesRegex(AssertionError, "local identity/direction"):
            validate_tree(root)

    def test_disabled_alarm_and_stop_polarity_cannot_be_reversed(self):
        for uid, term, value in (("1619", "8741", "01"), ("50030", "49997", "0000")):
            root = deepcopy(self.original)
            unique(root, "diag", uid).find(
                f"nodeList/*/termList/*[@uid='{term}']/dco/ConstValue"
            ).text = value
            with self.assertRaises(AssertionError):
                validate_tree(root)
        root = deepcopy(self.original)
        unique(root, "whileLoop", "203").find("loopTestDCO/objFlags").text = "65536"
        with self.assertRaisesRegex(AssertionError, "Stop-if-True"):
            validate_tree(root)

    def test_wait_changed_or_hidden_operation_rejected(self):
        root = deepcopy(self.original)
        unique(root, "diag", "211").find(
            "nodeList/*/termList/*[@uid='24741']/dco/ConstValue"
        ).text = "00000051"
        with self.assertRaisesRegex(AssertionError, "wait literal"):
            validate_tree(root)
        root = deepcopy(self.original)
        extra = deepcopy(unique(root, "gRef", "50011"))
        extra.set("uid", "999999")
        unique(root, "diag", "49991").find("zPlaneList").append(extra)
        with self.assertRaisesRegex(AssertionError, "operations"):
            validate_tree(root)


if __name__ == "__main__":
    unittest.main()
