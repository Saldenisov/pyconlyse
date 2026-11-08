"""Discriminating source semantics, caller axes, and enum-default gates."""

import ast
import copy
import inspect
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from legacy.trancon_client.candidates.cleaning import candidate, experiment_candidate, selection_candidate
from legacy.trancon_client.candidates.cleaning.clean_kinetics_sd import clean_kinetics_sd
from lvkit.codegen.builder import _param_default_expr
from lvkit.models import LVType, LVTypeKind, Terminal


class EnumDefaultCompilerTests(unittest.TestCase):
    def test_saved_nonzero_default(self):
        enum = LVType(kind=LVTypeKind.ENUM, underlying_type="UnitUInt32")
        term = Terminal(id="enum", index=0, direction="input", lv_type=enum, default_value="1")
        self.assertEqual(ast.literal_eval(_param_default_expr(term)), 1)

    def test_saved_zero_and_unspecified_defaults(self):
        enum = LVType(kind=LVTypeKind.ENUM, underlying_type="UnitUInt16")
        for default in ("0", None):
            term = Terminal(id="enum", index=0, direction="input", lv_type=enum, default_value=default)
            self.assertEqual(ast.literal_eval(_param_default_expr(term)), 0)

    def test_numeric_scalar_default_unchanged(self):
        number = LVType(kind=LVTypeKind.PRIMITIVE, underlying_type="NumUInt32")
        term = Terminal(id="number", index=0, direction="input", lv_type=number, default_value="17")
        self.assertEqual(ast.literal_eval(_param_default_expr(term)), 17)

    def test_helper_default_selects_approx_without_deleting(self):
        self.assertEqual(inspect.signature(clean_kinetics_sd).parameters["clean_mode"].default, 1)
        out = clean_kinetics_sd(data=[[2.], [100.], [8.]], kinetics=[2., 100., 8.],
                                timedelays=[0., 1., 2.], tdpixels=(0, 2), bounds=(0., 10.))
        self.assertEqual(out.timedelays_out, [0., 1., 2.])
        self.assertEqual(out.data_out, [[2., 5., 8.]])


class CleaningCandidateTests(unittest.TestCase):
    def test_caller_mean_of_selected_columns_and_return_axes(self):
        data = [[0., 2., 999.], [100., 102., -999.], [4., 6., 777.]]
        out = experiment_candidate(data, [-1., 0., 100.], (0, 1), (0, 2), (0., 10.))
        self.assertEqual(out.kinetics, [1., 101., 5.])
        self.assertEqual(out.data, [[0., 2., 999.], [2., 4., 888.], [4., 6., 777.]])
        self.assertEqual(out.timedelays, [-1., 0., 100.])

    def test_adjacent_approx_uses_updated_previous_neighbor(self):
        data = [[0., 0.], [100., 1000.], [300., 3000.], [8., 80.]]
        out = experiment_candidate(data, [0., 1., 2., 3.], (0, 0), (0, 3), (-1., 10.))
        self.assertEqual(out.data, [[0., 0.], [150., 1500.], [79., 790.], [8., 80.]])
        self.assertNotEqual(out.data[2], [54., 540.])

    def test_delete_adjusts_later_indices_and_matching_delays(self):
        out = experiment_candidate([[0., 10.], [100., 20.], [3., 30.], [200., 40.], [8., 50.]],
                                    [-5., 0., 1., 2., 100.], (0, 0), (0, 4), (-1., 10.), "delete")
        self.assertEqual(out.data, [[0., 10.], [3., 30.], [8., 50.]])
        self.assertEqual(out.timedelays, [-5., 1., 100.])

    def test_inclusive_delay_interval_strict_od_bounds(self):
        data = [[float(i)] for i in range(6)]
        out = candidate(data, [-99., 1., 2., 3., 99., 100.], list(range(6)), (1, 4), (1., 3.), "delete")
        self.assertEqual(out.data_out, [[0., 1., 2., 3., 5.]])
        self.assertEqual(out.timedelays_out, [0, 1, 2, 3, 5])

    def test_nan_not_flagged_but_infinities_flagged(self):
        data = [[float(i)] for i in range(5)]
        out = candidate(data, [0., math.nan, math.inf, -math.inf, 1.], list(range(5)), (0, 4), (0., 1.), "delete")
        self.assertEqual(out.data_out, [[0., 1., 4.]])
        self.assertEqual(out.timedelays_out, [0, 1, 4])

    def test_boundaries_copy_neighbor_and_singleton_uses_default_zero(self):
        out = candidate([[100.], [4.], [200.]], [100., 4., 200.], [0., 1., 2.], (0, 2), (0., 10.))
        self.assertEqual(out.data_out, [[4., 4., 4.]])
        out = candidate([[100.]], [100.], [0.], (0, 0), (0., 10.))
        self.assertEqual(out.data_out, [[0.]])

    def test_delay_spacing_does_not_weight_approximation(self):
        data, kin = [[2.], [100.], [8.]], [2., 100., 8.]
        a = candidate(data, kin, [0., 1., 2.], (0, 2), (0., 10.))
        b = candidate(data, kin, [0., 1., 1000.], (0, 2), (0., 10.))
        self.assertEqual(a.data_out, b.data_out)
        self.assertEqual(a.data_out, [[2., 5., 8.]])

    def test_no_flags_still_returns_helper_transpose(self):
        out = candidate([[1., 10.], [2., 20.]], [1., 2.], [0., 1.], (0, 1), (1., 2.), "delete")
        self.assertEqual(out.data_out, [[1., 2.], [10., 20.]])
        self.assertEqual(out.timedelays_out, [0., 1.])

    def test_delete_all_rows_returns_empty_axes(self):
        out = experiment_candidate([[100., 200.], [300., 400.]], [0., 1.], (0, 0), (0, 1), (0., 10.), "delete")
        self.assertEqual(out.data, [])
        self.assertEqual(out.timedelays, [])

    def test_input_and_axis_not_mutated_or_aliased(self):
        data, kin, delays = [[2., 20.], [100., 1000.], [8., 80.]], [2., 100., 8.], [0., 1., 2.]
        before = copy.deepcopy((data, kin, delays))
        out = candidate(data, kin, delays, (0, 2), (0., 10.))
        out.timedelays_out[0] = -999.
        out.data_out[0][0] = -999.
        self.assertEqual((data, kin, delays), before)

    def test_caller_preserves_nonfinite_mean(self):
        actual = selection_candidate([[math.nan, 2.], [math.inf, -math.inf], [4., 6.]], (0, 1))
        self.assertTrue(math.isnan(actual[0]) and math.isnan(actual[1]))
        self.assertEqual(actual[2], 5.)

    def test_unqualified_caller_precision_and_single_column_rejected(self):
        for data in ([[1.1, 2.]], [[1.]], [[1e40, 2.]]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                selection_candidate(data, (0, 0))

    def test_unqualified_shapes_bounds_and_modes_rejected(self):
        values = dict(data=[[1., 2.], [3., 4.]], kinetics=[1., 3.], timedelays=[0., 1.],
                      delay_pixels=(0, 1), od_bounds=(0., 10.))
        invalid = [{"data": []}, {"data": [[1.], [2., 3.]]}, {"data": [[True, 2.], [3., 4.]]},
                   {"kinetics": [1.]}, {"timedelays": [0., math.inf]},
                   {"delay_pixels": (1, 0)}, {"delay_pixels": (0, 2)},
                   {"delay_pixels": (False, 1)}, {"delay_pixels": (0., 1)},
                   {"od_bounds": (2., 1.)}, {"od_bounds": (0., math.nan)}, {"mode": "interpolate"}]
        for override in invalid:
            with self.subTest(override=override), self.assertRaises(ValueError):
                candidate(**{**values, **override})


if __name__ == "__main__":
    unittest.main(verbosity=2)
