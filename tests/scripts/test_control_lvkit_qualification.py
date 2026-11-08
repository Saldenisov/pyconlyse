"""Generic converter regressions discovered in Supervision/TRANCON fixtures."""

from __future__ import annotations

import copy
import math
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
from inventory_control_lvkit import inspect_generated, inventory  # noqa: E402
from qualify_control_lvkit import (  # noqa: E402
    DEFAULT_CHECKOUT,
    PROFILES,
    audit_pure,
    qualify,
    validate_log,
    validate_vacuum,
    verify_checkout,
)


class ControlConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        verify_checkout(DEFAULT_CHECKOUT)

    def test_exhaustive_supervision_vacuum(self):
        source, result = qualify("supervision_vacuum")
        self.assertEqual(result["differential_cases"], 8192)
        self.assertFalse(result["deployable"])
        self.assertIn("not c5_in_dio96[2]", source)

    def test_trancon_generated_log_matches_independent_numpy(self):
        source, result = qualify("trancon_log")
        self.assertEqual(result["differential_cases"], 270)
        self.assertIn("_lv.real64_divide(1.0, transmission)", source)
        self.assertIn("output_logxlog1x", source)
        self.assertFalse(result["native_runtime_equivalence"])

    def test_source_wire_mutations_rejected(self):
        from lvkit.extractor import extract_vi_xml

        for name, validator in (
            ("trancon_log", validate_log),
            ("supervision_vacuum", validate_vacuum),
        ):
            path = PROFILES[name].get("parse_copy", PROFILES[name]["source"])
            root = ET.parse(extract_vi_xml(path)[0]).getroot()
            changed = copy.deepcopy(root)
            signal = changed.find(".//signalList/*")
            signal.find("termList/*").set("uid", "999999")
            with (
                self.subTest(profile=name),
                self.assertRaisesRegex(AssertionError, "missing source wire"),
            ):
                validator(changed)

    def test_runtime_division_edges(self):
        from lvkit.runtime import lv

        for a, b, expected in (
            (1, 0.0, math.inf),
            (1, -0.0, -math.inf),
            (-1, -0.0, math.inf),
            (0, 0, math.nan),
            (math.nan, 0, math.nan),
            (math.inf, math.inf, math.nan),
            (6, 2, 3.0),
        ):
            actual = lv.real64_divide(a, b)
            with self.subTest(a=a, b=b):
                self.assertTrue(math.isnan(actual)) if math.isnan(
                    expected
                ) else self.assertEqual(actual, expected)
        self.assertEqual(lv.real64_divide(8.0, [[2.0], [4.0]]), [[4.0], [2.0]])

    def test_log_real_domain_and_nested_arrays(self):
        from lvkit.runtime import lv

        self.assertEqual(lv.log10([[1.0, 10.0], [100.0]]), [[0.0, 1.0], [2.0]])
        self.assertEqual(lv.log10(-0.0), -math.inf)
        self.assertTrue(math.isnan(lv.log10(-1.0)))
        self.assertTrue(math.isnan(lv.log10(math.nan)))

    def test_log_codegen_rejects_non_dbl(self):
        from lvkit.codegen.nodes.base import CodeGenError
        from lvkit.codegen.nodes.ops.real64_log10 import real64_log10
        from lvkit.graph.models import PrimitiveNode
        from lvkit.models import LVType, LVTypeKind, Terminal

        for kind in ("NumFloat32", "NumComplex128", "NumInt32"):
            node = PrimitiveNode(
                id="n",
                vi_path="test.vi",
                terminals=[
                    Terminal(
                        id="t",
                        index=1,
                        direction="input",
                        lv_type=LVType(LVTypeKind.PRIMITIVE, underlying_type=kind),
                    )
                ],
            )
            with self.subTest(kind=kind), self.assertRaises(CodeGenError):
                real64_log10(node, None)

    def test_result_field_normalization_and_error_only_annotation(self):
        from lvkit.codegen.builder import build_function_def, result_field_name

        self.assertEqual(result_field_name("-log(x)=log(1/x)"), "output_logxlog1x")
        fn = build_function_def(
            SimpleNamespace(
                name="OnlyError.vi",
                outputs=[SimpleNamespace(is_error_cluster=True)],
                inputs=[],
            ),
            "OnlyError.vi",
            [],
        )
        self.assertIsNone(fn.returns)

    def test_graph_clear_drops_reviewed_binding_scope(self):
        from lvkit.graph import InMemoryVIGraph

        graph = InMemoryVIGraph()
        graph.reviewed_local_bindings["old.vi::1"] = "old.vi::2"
        graph.clear()
        self.assertEqual(graph.reviewed_local_bindings, {})

    def test_radioprotection_conditional_output_rejected(self):
        from lvkit.codegen.builder import build_module
        from lvkit.codegen.nodes.base import UnknownNodeError
        from lvkit.graph import InMemoryVIGraph, LoadMode
        from lvkit.reviewed_locals import configure_reviewed_locals

        path = (
            PROFILES["supervision_vacuum"]["source"].parent
            / "2_SUP_Graph _Radioprot.vi"
        )
        graph = InMemoryVIGraph()
        key = graph.load_vi(path, mode=LoadMode.NONE)
        # Native BTIM local and Boolean/graph type signatures corroborate
        # these mappings. Branch persistence is explicitly NOT qualified.
        configure_reviewed_locals(
            graph, key, {"520": "518", "382": "2097", "46": "2403"}
        )
        with self.assertRaisesRegex(UnknownNodeError, "persistent-state model"):
            build_module(graph.get_vi_context(key), key, graph=graph)

    def test_generated_execution_gate_rejects_network_and_dunder(self):
        source, _ = qualify("trancon_log")
        for changed in (
            "import socket\n" + source,
            source.replace("_lv.log10(quotient)", "_lv.__class__(quotient)"),
            source.replace("_lv.log10(quotient)", "open(quotient)"),
        ):
            with self.assertRaises(AssertionError):
                audit_pure(changed, "trancon_log")

    def test_quarantine_marker_absence_is_not_qualification(self):
        self.assertEqual(inspect_generated("def f(x):\n    return x\n"), {})
        rows = inventory()
        self.assertEqual(sum(r["corpus"] == "supervision" for r in rows), 38)
        self.assertEqual(sum(r["corpus"] == "trancon" for r in rows), 334)
        self.assertTrue(
            any(r["manual_evidence"] == "NO_WIRE_RECORD_IN_CLIENT_AUDIT" for r in rows)
        )


if __name__ == "__main__":
    unittest.main()
