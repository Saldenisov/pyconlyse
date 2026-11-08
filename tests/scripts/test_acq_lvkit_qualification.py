"""Pure converter qualification, source-wire mutations and execution gates."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_lvkit import (  # noqa: E402
    ARCHIVE,
    DEFAULT_CHECKOUT,
    DEFAULT_SOURCE,
    audit_generated,
    qualify,
    verify_checkout,
)
from validate_acq_deviation_helpers import (  # noqa: E402
    PROFILES,
    checked_roots,
    unique,
    validate_tree,
)


class SourceWireQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.roots = checked_roots(ARCHIVE)

    def test_both_original_helper_wires(self):
        for name, profile in PROFILES.items():
            self.assertEqual(
                len(validate_tree(self.roots[name], profile)), profile["channels"]
            )

    def test_false_phase_flag_mutation_rejected(self):
        root = copy.deepcopy(self.roots["direct"])
        constant = next(n for n in root.iter("ConstValue") if n.text == "0000")
        constant.text = "0001"
        with self.assertRaisesRegex(AssertionError, "literal False"):
            validate_tree(root, PROFILES["direct"])

    def test_wrong_nested_lane_mutation_rejected(self):
        root = copy.deepcopy(self.roots["direct"])
        unique(root, "nMux", "1555").findall("termList/*")[2].find("dco/i").text = "4"
        with self.assertRaisesRegex(AssertionError, "orange nested indices"):
            validate_tree(root, PROFILES["direct"])

    def test_primitive_mutation_rejected(self):
        root = copy.deepcopy(self.roots["deviated"])
        unique(root, "prim", "1400").find("primResID").text = "1111"
        with self.assertRaisesRegex(AssertionError, "opcode census"):
            validate_tree(root, PROFILES["deviated"])

    def test_local_binding_bank_mutation_rejected(self):
        root = copy.deepcopy(self.roots["direct"])
        unique(root, "gRef", "1336").find("termList/*/dco/paramIdx").text = "1"
        with self.assertRaisesRegex(AssertionError, "bank index"):
            validate_tree(root, PROFILES["direct"])

    def test_missing_copy_wire_rejected(self):
        root = copy.deepcopy(self.roots["direct"])
        signals = unique(root, "diag", "5910").find("signalList")
        for signal in list(signals):
            if any(t.get("uid") == "5934" for t in signal.findall("termList/*")):
                signals.remove(signal)
        with self.assertRaisesRegex(AssertionError, "frame 0"):
            validate_tree(root, PROFILES["direct"])


SAFE_SOURCE = """from typing import Any, NamedTuple
class Result(NamedTuple):
    cluster: tuple
def helper(threshold: float=0.5, cluster: tuple=None) -> Result:
    return Result(cluster=cluster)
"""


class GeneratedExecutionGateTests(unittest.TestCase):
    def test_unpatched_direct_and_ni6602_outputs_are_not_executable_candidates(self):
        artifacts = REPO / "legacy/xp_acq_agent/data/converter_qualification/20261003"
        for filename in ("baseline_direct.py.txt", "rejected_ni6602.py.txt"):
            with self.subTest(filename=filename), self.assertRaises(AssertionError):
                audit_generated((artifacts / filename).read_text(encoding="utf-8"))

    def test_small_pure_grammar_accepted(self):
        self.assertEqual(audit_generated(SAFE_SOURCE)[1], "helper")

    def test_hardware_network_and_process_imports_rejected(self):
        for forbidden in ("socket", "nidaqmx", "serial", "subprocess", "os"):
            with self.subTest(forbidden=forbidden), self.assertRaises(AssertionError):
                audit_generated("import " + forbidden + "\n" + SAFE_SOURCE)

    def test_arbitrary_call_rejected(self):
        for expression in (
            "open('x')",
            "eval('1')",
            "__import__('socket')",
            "cluster.send(1)",
        ):
            with self.subTest(expression=expression), self.assertRaises(AssertionError):
                audit_generated(
                    SAFE_SOURCE.replace(
                        "    return", "    " + expression + "\n    return"
                    )
                )

    def test_unresolved_none_output_rejected(self):
        with self.assertRaisesRegex(AssertionError, "None output"):
            audit_generated(
                SAFE_SOURCE.replace("Result(cluster=cluster)", "Result(cluster=None)")
            )

    def test_loop_and_empty_placeholder_rejected(self):
        for fragment in ("    while True:\n        pass\n", "    pass\n"):
            with self.assertRaises(AssertionError):
                audit_generated(
                    SAFE_SOURCE.replace("    return", fragment + "    return")
                )


class PatchedConverterDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_CHECKOUT.exists():
            raise unittest.SkipTest("pinned lvkit checkout unavailable")
        verify_checkout(DEFAULT_CHECKOUT)

    def test_original_direct_helper_234_fixtures(self):
        _, result = qualify("direct", DEFAULT_CHECKOUT, DEFAULT_SOURCE)
        self.assertEqual(result["differential_cases"], 234)
        self.assertFalse(result["hardware_executed"])

    def test_original_deviated_helper_230_fixtures(self):
        _, result = qualify("deviated", DEFAULT_CHECKOUT, DEFAULT_SOURCE)
        self.assertEqual(result["differential_cases"], 230)

    def test_nested_copy_is_by_value_and_preserves_untargeted_branches(self):
        from lvkit.positional_cluster import replace_fields

        original = ((1, 2, 3), (4, 5, 6))
        result = replace_fields(original, (((0, 1), 99),))
        self.assertEqual(result, ((1, 99, 3), (4, 5, 6)))
        self.assertEqual(original, ((1, 2, 3), (4, 5, 6)))
        self.assertIs(result[1], original[1])

    def test_unreviewed_or_invalid_binding_is_rejected(self):
        from lvkit.graph import InMemoryVIGraph, LoadMode
        from lvkit.reviewed_locals import configure_reviewed_locals

        graph = InMemoryVIGraph()
        key = graph.load_vi(
            DEFAULT_SOURCE / PROFILES["direct"]["member"], mode=LoadMode.NONE
        )
        for bindings in (
            {},
            dict.fromkeys(PROFILES["direct"]["locals"], "not-a-terminal"),
            dict.fromkeys(PROFILES["direct"]["locals"], "1741"),
        ):
            with self.assertRaises(ValueError):
                configure_reviewed_locals(graph, key, bindings)


if __name__ == "__main__":
    unittest.main()
