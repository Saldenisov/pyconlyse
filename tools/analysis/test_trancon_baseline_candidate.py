"""Candidate source semantics and Array Subset compiler regression gates."""

import ast
import copy
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legacy.trancon_client.candidates.baseline import candidate
from lvkit.codegen.nodes.array_subset_node import generate
from lvkit.codegen.nodes.base import CodeGenError
from lvkit.graph.models import PrimitiveNode
from lvkit.models import LVType, LVTypeKind, Terminal
from lvkit.runtime import lv


class Context:
    def __init__(self, values, wired):
        self.values, self.array_vars = values, set()
        self.graph = SimpleNamespace(terminal_is_wired=lambda uid: uid in wired)

    def resolve(self, uid):
        return self.values.get(uid)

    def make_output_var(self, *_args):
        return "result"


def pane(rank):
    integer = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="NumInt32")
    number = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="NumFloat64")
    array = LVType(kind=LVTypeKind.ARRAY, dimensions=rank, element_type=number)
    terms = [Terminal(id="t0", index=0, direction="input", lv_type=array),
             Terminal(id="t1", index=1, direction="output", lv_type=array)]
    terms.extend(Terminal(id=f"t{i}", index=i, direction="input", lv_type=integer)
                 for i in range(2, 2 + 2 * rank))
    return PrimitiveNode(id="subset", vi_path="fixture.vi", node_type="subset", terminals=terms)


def evaluate(fragment, bindings):
    tree = ast.fix_missing_locations(ast.Module(body=fragment.statements, type_ignores=[]))
    namespace = {"_lv": lv, **bindings}
    exec(compile(tree, "<subset-regression>", "exec"), namespace)
    return namespace["result"]


class SubsetCompilerTests(unittest.TestCase):
    def test_second_axis_subset_retains_unwired_first_axis_length(self):
        ctx = Context({"t0": "data", "t2": "0", "t4": "1", "t5": "2"}, {"t0", "t2", "t4", "t5"})
        result = evaluate(generate(pane(2), ctx), {"data": [[1, 2, 3, 4], [10, 20, 30, 40]]})
        self.assertEqual(result, [[2, 3], [20, 30]])

    def test_independent_three_axis_bounds(self):
        data = [[[100*a+10*b+c for c in range(4)] for b in range(3)] for a in range(2)]
        ctx = Context({"t0": "data", "t2": "1", "t3": "1", "t4": "1",
                       "t5": "2", "t6": "2", "t7": "1"}, {"t0", *[f"t{i}" for i in range(2, 8)]})
        self.assertEqual(evaluate(generate(pane(3), ctx), {"data": data}), [[[112], [122]]])

    def test_single_axis_unwired_length(self):
        ctx = Context({"t0": "data", "t2": "1"}, {"t0", "t2"})
        self.assertEqual(evaluate(generate(pane(1), ctx), {"data": [2, 4, 6]}), [4, 6])

    def test_incomplete_pane_rejected(self):
        node = pane(2)
        node.terminals.pop()
        with self.assertRaisesRegex(CodeGenError, "pane"):
            generate(node, Context({"t0": "data"}, {"t0"}))

    def test_unresolved_wired_boundary_rejected(self):
        with self.assertRaisesRegex(CodeGenError, "unresolved"):
            generate(pane(2), Context({"t0": "data"}, {"t0", "t4"}))


class BaselineCandidateTests(unittest.TestCase):
    def test_discriminating_scalar_tunnel_and_delay_truncation(self):
        # Mean background spectrum = [2, 20]. Indexed tunnel pairs its scalar
        # elements with delay rows and caps loop iterations at min(3, 2).
        data = [[1., 10.], [3., 30.], [9., 90.]]
        actual = candidate(data, 0, 1)
        self.assertEqual(actual, [[-1., 8.], [-17., 10.]])
        expected_spectrum_subtraction = [[-1., -10.], [1., 10.], [7., 70.]]
        self.assertNotEqual(actual, expected_spectrum_subtraction)

    def test_wavelength_dimension_exceeding_delays_does_not_add_rows(self):
        self.assertEqual(candidate([[1., 2., 3.], [5., 6., 7.]], 0, 1),
                         [[-2., -1., 0.], [1., 2., 3.]])

    def test_reversed_and_equal_interior_bounds(self):
        data = [[1., 10.], [3., 30.], [9., 90.]]
        self.assertEqual(candidate(data, 1, 0), candidate(data, 0, 1))
        self.assertEqual(candidate(data, 0, 0), candidate(data, 0, 1))
        self.assertEqual(candidate(data, 1, 1), candidate(data, 1, 2))

    def test_nonfinite_is_not_ignored(self):
        output = candidate([[math.nan, 2., 4.], [6., 8., 10.]], 0, 1)
        self.assertTrue(all(math.isnan(x) for x in output[0]))
        self.assertEqual(output[1], [1., 3., 5.])
        output = candidate([[math.inf, 2.], [6., 8.]], 0, 1)
        self.assertTrue(math.isnan(output[0][0]))
        self.assertEqual(output[0][1], -math.inf)

    def test_source_rows_not_mutated(self):
        data = [[1., 10.], [3., 30.], [9., 90.]]
        original = copy.deepcopy(data)
        candidate(data, 0, 1)
        self.assertEqual(data, original)

    def test_unqualified_boundaries_rejected(self):
        for low, high in [(2, 2), (-1, 1), (0, 3), (0.5, 1), (False, 1)]:
            with self.subTest(low=low, high=high), self.assertRaises(ValueError):
                candidate([[1., 10.], [3., 30.], [9., 90.]], low, high)

    def test_empty_or_ragged_map_rejected(self):
        for data in [[], [[]], [[1.], [2., 3.]], [["bad"], [2.]], [[True], [2.]]]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                candidate(data, 0, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
