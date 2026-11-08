"""NI6602 numeric representation profile, with no LabVIEW or hardware execution."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools"))

from qualify_acq_lvkit import DEFAULT_CHECKOUT, verify_checkout  # noqa: E402

verify_checkout(DEFAULT_CHECKOUT)

from DeviceServers.control.elyse_acq.vi_simulation.write_ni6602 import (  # noqa: E402
    labview_i32_to_u32_ticks,
    labview_u32_ticks,
)
from lvkit.codegen.context import CodeGenContext  # noqa: E402
from lvkit.codegen.nodes import property_node  # noqa: E402
from lvkit.codegen.nodes.base import CodeGenError  # noqa: E402
from lvkit.graph import InMemoryVIGraph  # noqa: E402
from lvkit.graph.models import PrimitiveNode  # noqa: E402
from lvkit.models import LVType, LVTypeKind, Terminal  # noqa: E402
from qualify_acq_counter_numeric import (  # noqa: E402
    audit_numeric,
    documented_ticks,
    numeric_fragment,
    qualify,
    run_numeric,
    vectors,
)


def coercion_fixture(source_type):
    """The emitter sees a typed graph source, not a bound-value guess."""
    target_type = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="NumUInt32")
    source_lv_type = (
        None
        if source_type is None
        else LVType(kind=LVTypeKind.PRIMITIVE, underlying_type=source_type)
    )
    source = Terminal(id="out", index=0, direction="output", lv_type=source_lv_type)
    target = Terminal(id="in", index=0, direction="input", lv_type=target_type)
    producer = PrimitiveNode(id="producer", vi_path="synthetic.vi", terminals=[source])
    consumer = PrimitiveNode(id="consumer", vi_path="synthetic.vi", terminals=[target])
    graph = InMemoryVIGraph()
    for node in (producer, consumer):
        graph._graph.add_node(node.id, node=node)
        for term in node.terminals:
            graph._term_to_node[term.id] = node.id
    # incoming_edges uses node/terminal identities; other fields are irrelevant
    # to this component fixture and are not a parsing qualification.
    edge = SimpleNamespace(node_id="producer", terminal_id="out", index=0)
    graph._graph.add_edge(
        "producer", "consumer", source=edge, dest=SimpleNamespace(terminal_id="in")
    )
    return consumer, target, CodeGenContext(graph=graph), edge


class AcqCounterNumericTests(unittest.TestCase):
    def test_4143_documented_vectors_match_generated_and_manual_model(self):
        receipt = qualify()["receipt"]
        self.assertEqual(receipt["numeric_cases"], 4143)
        self.assertEqual(receipt["scalar_conversions_compared"], 8286)
        self.assertFalse(receipt["deployable"])
        self.assertFalse(receipt["full_writer_qualified"])
        self.assertFalse(receipt["vi_executed"])

    def test_original_chain_contains_two_i32_casts_three_u32_masks(self):
        source, attrs, temporaries, receipt = numeric_fragment()
        tree = audit_numeric(source, attrs, temporaries)
        self.assertEqual(len(tree.body), 5)
        self.assertEqual(sum(isinstance(n, ast.BitAnd) for n in ast.walk(tree)), 3)
        self.assertEqual(
            receipt["archived_numeric_type_proof"]["163"]["type"], "NumInt32"
        )
        self.assertEqual(
            receipt["timing_bindings"], {"3088": "task", "3094": "supplied_error"}
        )

    def test_ties_signed_bits_and_finite_saturation(self):
        cases = (
            (-0.05, 4294967295),
            (-0.075, 4294967294),
            (-0.025, 0),
            (0.025, 0),
            (0.075, 2),
            (0.125, 2),
            (0.16, 3),
            (2147483648 / 20.0, 2147483647),
            (-2147483649 / 20.0, 2147483648),
            (1e300, 2147483647),
            (-1e300, 2147483648),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(labview_i32_to_u32_ticks(value), expected)
                self.assertEqual(documented_ticks(value), expected)

    def test_historical_u32_shortcut_is_not_saved_i32_path(self):
        value = 2147483648 / 20.0
        self.assertEqual(labview_u32_ticks(value), 2147483648)
        self.assertEqual(labview_i32_to_u32_ticks(value), 2147483647)
        with self.assertRaises(ValueError):
            labview_u32_ticks(-0.05)
        self.assertEqual(labview_i32_to_u32_ticks(-0.05), 4294967295)

    def test_nonfinite_values_are_python_rejections_not_legacy_claims(self):
        for value in (
            float("nan"),
            float("inf"),
            -float("inf"),
            1e308,
            10**1000,
            True,
            "1",
        ):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                labview_i32_to_u32_ticks(value)
        source, attrs, temporaries, _ = numeric_fragment()
        for value in (float("nan"), float("inf"), 1e308):
            with self.assertRaisesRegex(AssertionError, "finite DBL"):
                run_numeric(source, attrs, temporaries, value, 1.0)

    def test_i32_property_wire_preserves_bits_and_expression_precedence(self):
        node, term, ctx, _ = coercion_fixture("NumInt32")
        expression = property_node._u32_write_value(node, term, ctx, "a + b")
        self.assertIsInstance(expression, ast.BinOp)
        tree = ast.fix_missing_locations(ast.Expression(expression))
        self.assertEqual(
            eval(
                compile(tree, "<synthetic-coercion>", "eval"),
                {"__builtins__": {}, "a": -2, "b": 1},
            ),
            4294967295,
        )

    def test_matching_u32_property_does_not_cast(self):
        node, term, ctx, _ = coercion_fixture("NumUInt32")
        self.assertEqual(
            ast.unparse(property_node._u32_write_value(node, term, ctx, "value")),
            "value",
        )

    def test_unqualified_or_missing_numeric_source_rejected(self):
        for source_type in (None, "NumFloat64", "NumInt64", "NumUInt16", "Boolean"):
            node, term, ctx, _ = coercion_fixture(source_type)
            with self.subTest(source_type=source_type), self.assertRaises(CodeGenError):
                property_node._u32_write_value(node, term, ctx, "value")

    def test_ambiguous_property_source_rejected(self):
        node, term, ctx, edge = coercion_fixture("NumInt32")
        ctx.graph._graph.add_edge(
            "producer", "consumer", source=edge, dest=SimpleNamespace(terminal_id="in")
        )
        with self.assertRaisesRegex(CodeGenError, "ambiguous"):
            property_node._u32_write_value(node, term, ctx, "value")

    def test_removed_mask_is_detected_by_negative_vector(self):
        source, attrs, temporaries, _ = numeric_fragment()
        mutated = source.replace(" & 4294967295", "")
        self.assertEqual(run_numeric(mutated, attrs, temporaries, -0.05, 0.1)[0], -1)
        self.assertNotEqual(
            run_numeric(mutated, attrs, temporaries, -0.05, 0.1)[0],
            documented_ticks(-0.05),
        )

    def test_audit_rejects_imports_calls_reads_and_extra_assignment(self):
        source, attrs, temporaries, _ = numeric_fragment()
        for mutated in (
            "import nidaqmx\n" + source,
            source.replace("round(", "open("),
            source.replace("20.0 * delay_us", "task.__class__"),
            source + "task.start()\n",
            source.replace("long_integer =", "round =", 1),
        ):
            with self.subTest(mutated=mutated), self.assertRaises(AssertionError):
                audit_numeric(mutated, attrs, temporaries)

    def test_vector_generation_is_reproducible_and_exercises_both_signs(self):
        self.assertEqual(vectors(), vectors())
        self.assertEqual(len(vectors()), 4143)
        self.assertTrue(any(d < 0 < w for d, w in vectors()))


if __name__ == "__main__":
    unittest.main()
