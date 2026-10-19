"""Saved empty registers and supplied native-return boundaries, not reset claims."""

import math
import unittest
from dataclasses import FrozenInstanceError

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    UNSUPPLIED,
    ErrorCluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.ni6220_runtime import (
    completed_iteration,
    counter_frame,
    point_frame,
)
from DeviceServers.control.elyse_acq.vi_simulation.saved_measurement_data import (
    saved_source_measurement_snapshot,
)
from DeviceServers.control.elyse_acq.vi_simulation.vam_status import (
    first_frame_from_conversion,
    second_frame,
    second_frame_from_conversions,
)


class SavedMeasurementBusinessTests(unittest.TestCase):
    def arguments(self, *, current=5.5, previous=math.nan):
        saved = saved_source_measurement_snapshot()
        return dict(
            reader_values=tuple(float(i) for i in range(10)),
            bank65=saved.bank65,
            bank66=saved.bank66,
            bank67=saved.bank67,
            current_mean_return=current,
            previous_mean_return=previous,
            counter_selector_snapshot=saved.bank68,
            increment_read_snapshot=saved.bank68,
            increment_return=1,
        )

    def test_saved_fixture_is_immutable_and_not_a_four_zero_array(self):
        saved = saved_source_measurement_snapshot()
        self.assertEqual(
            (saved.bank59, saved.bank65, saved.bank66, saved.bank67), ((),) * 4
        )
        self.assertEqual((saved.bank62, saved.bank63, saved.bank68), (0, 0, 0))
        with self.assertRaises(FrozenInstanceError):
            saved.bank68 = 3

    def test_explicit_nan_mean_of_empty_selects_false_without_starting_capture(self):
        result = counter_frame(**self.arguments())
        self.assertFalse(result.threshold_true)
        self.assertEqual(result.counter_diagram_uid, "104729")
        self.assertEqual(result.counter_after, 0)
        self.assertFalse(result.counter_written)
        self.assertEqual(result.bank65_previous, (4.0, 5.0, 6.0, 7.0))
        self.assertEqual((result.bank66_captured, result.bank67_before_rise), ((), ()))

    def test_finite_empty_mean_fixture_can_start_counter_but_preserves_empty_baseline(
        self,
    ):
        result = counter_frame(**self.arguments(previous=0.0))
        self.assertTrue(result.threshold_true)
        self.assertEqual(result.counter_diagram_uid, "81862")
        self.assertEqual(result.counter_after, 1)
        self.assertEqual((result.bank66_captured, result.bank67_before_rise), ((), ()))

    def test_first_frame_replaces_prior_array_without_resetting_later_capture_arrays(
        self,
    ):
        first = counter_frame(**self.arguments())
        args = self.arguments(current=6.0, previous=5.5)
        args["reader_values"] = tuple(float(i) + 0.5 for i in range(10))
        args.update(
            bank65=first.bank65_previous,
            bank66=first.bank66_captured,
            bank67=first.bank67_before_rise,
        )
        second = counter_frame(**args)
        self.assertEqual(second.bank67_before_rise, first.bank65_previous)
        self.assertEqual(second.bank66_captured, ())
        self.assertEqual(second.counter_after, 1)

    def test_counter_three_captures_current_without_fabricating_previous_array(self):
        for previous in (math.nan, 0.0):
            args = self.arguments(previous=previous)
            args["counter_selector_snapshot"] = 3
            result = counter_frame(**args)
            self.assertEqual(result.bank66_captured, (4.0, 5.0, 6.0, 7.0))
            self.assertEqual(result.bank67_before_rise, ())
            self.assertEqual(result.counter_after, 0)

    def test_true_counter_one_still_unresolved_even_with_empty_source_fixture(self):
        args = self.arguments(previous=0.0)
        args["counter_selector_snapshot"] = 1
        result = counter_frame(**args)
        self.assertIs(result.counter_after, UNSUPPLIED)
        self.assertIs(result.bank66_captured, UNSUPPLIED)
        self.assertEqual(result.bank67_before_rise, ())

    def test_variable_length_prior_arrays_are_not_implicitly_normalized(self):
        for length in range(7):
            args = self.arguments(previous=0.0)
            array = tuple(float(i + 100) for i in range(length))
            args.update(bank65=array, bank66=array, bank67=array)
            result = counter_frame(**args)
            self.assertEqual(result.bank67_before_rise, array)
            self.assertEqual(result.bank66_captured, array)
            self.assertEqual(len(result.bank65_previous), 4)

    def test_saved_display_index_selects_first_supplied_mean(self):
        saved = saved_source_measurement_snapshot()
        result = point_frame(
            reader_values=(), point_mean_returns=(9.0,) * 6, bank63=saved.bank63
        )
        self.assertEqual(result.indicator, 9.0)
        self.assertEqual(result.bank59, (9.0,) * 6)
        self.assertEqual(tuple(call.input_value for call in result.calls), (0.0,) * 6)
        self.assertEqual(saved.bank59, ())

    def test_returned_read_fault_does_not_replace_empty_prior_mean_or_stop(self):
        args = self.arguments()
        args["reader_values"] = ()
        fault = ErrorCluster(True, -99, "supplied read fault")
        result = completed_iteration(
            read_error=fault,
            stop_snapshot=False,
            counter_arguments=args,
            point_arguments=dict(
                reader_values=(), point_mean_returns=(8.0,) * 6, bank63=0
            ),
        )
        self.assertTrue(result.keep_running)
        self.assertEqual(result.handler_error, fault)
        self.assertEqual(result.counter_frame.bank65_previous, (0.0,) * 4)
        self.assertEqual(result.counter_frame.bank66_captured, ())
        self.assertEqual(result.point_frame.bank59, (8.0,) * 6)

    def test_vam_startup_empty_arrays_require_three_distinct_conversion_returns(self):
        saved = saved_source_measurement_snapshot()
        first = first_frame_from_conversion(
            (0.0,) * 64,
            iteration=0,
            bank32=0,
            bank31=0,
            bank53=1.0,
            bank54=2.0,
            bank60=3.0,
            bank59=saved.bank59,
            array_to_cluster_return=tuple(float(i + 10) for i in range(8)),
        )
        result = second_frame_from_conversions(
            first.vam,
            bank62=saved.bank62,
            bank66=saved.bank66,
            bank67=saved.bank67,
            bank66_array_to_cluster_return=(20.0,) * 4,
            bank67_array_to_cluster_return=(30.0,) * 4,
        )
        self.assertEqual(result[12:19], tuple(float(i + 10) for i in range(7)))
        self.assertEqual(result[32:40], (20.0,) * 4 + (30.0,) * 4)
        self.assertEqual(result[10:12], (1.0, 2.0))
        self.assertEqual(result[20], 3.0)
        self.assertEqual(result[63], 0.0)
        with self.assertRaises(TypeError):
            second_frame(first.vam, bank62=0, bank66=(), bank67=())

    def test_vam_can_sample_new_max_and_old_empty_min_independently(self):
        result = second_frame_from_conversions(
            tuple(float(i) for i in range(64)),
            bank62=5,
            bank66=(4.0, 5.0, 6.0, 7.0),
            bank67=(),
            bank66_array_to_cluster_return=(4.0, 5.0, 6.0, 7.0),
            bank67_array_to_cluster_return=(-1.0,) * 4,
        )
        self.assertEqual(result[32:40], (4.0, 5.0, 6.0, 7.0) + (-1.0,) * 4)
        self.assertEqual(result[63], 5.0)

    def test_each_wcm_conversion_preserves_existing_entries_for_lengths_zero_to_six(
        self,
    ):
        for bank in (66, 67):
            for length in range(7):
                array = tuple(float(i + 100) for i in range(length))
                cluster = array[:4] + (999.0,) * max(0, 4 - length)
                args = dict(
                    bank62=0,
                    bank66=(),
                    bank67=(),
                    bank66_array_to_cluster_return=(1.0,) * 4,
                    bank67_array_to_cluster_return=(2.0,) * 4,
                )
                args[f"bank{bank}"] = array
                args[f"bank{bank}_array_to_cluster_return"] = cluster
                result = second_frame_from_conversions((0.0,) * 64, **args)
                start = 32 if bank == 66 else 36
                with self.subTest(bank=bank, length=length):
                    self.assertEqual(result[start : start + 4], cluster)
                    if length:
                        args[f"bank{bank}_array_to_cluster_return"] = (-100.0,) * 4
                        with self.assertRaises(ValueError):
                            second_frame_from_conversions((0.0,) * 64, **args)

    def test_conversion_arguments_remain_explicit_typed_and_fixed_size(self):
        arguments = dict(
            bank62=0,
            bank66=(),
            bank67=(),
            bank66_array_to_cluster_return=(1.0,) * 4,
            bank67_array_to_cluster_return=(2.0,) * 4,
        )
        for name in ("bank66", "bank67"):
            for value in ([1.0], (1,), (True,)):
                args = dict(arguments)
                args[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    second_frame_from_conversions((0.0,) * 64, **args)
        for name in (
            "bank66_array_to_cluster_return",
            "bank67_array_to_cluster_return",
        ):
            for value in ((), (1.0,) * 3, (1.0,) * 5, (True,) * 4):
                args = dict(arguments)
                args[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    second_frame_from_conversions((0.0,) * 64, **args)

    def test_conversion_nan_infinity_and_signed_zero_are_not_rejected_or_sanitized(
        self,
    ):
        values = (float("nan"), math.inf, -math.inf, -0.0)
        converted = (float("nan"), math.inf, -math.inf, -0.0)
        result = second_frame_from_conversions(
            (0.0,) * 64,
            bank62=0,
            bank66=values,
            bank67=(),
            bank66_array_to_cluster_return=converted,
            bank67_array_to_cluster_return=(0.0,) * 4,
        )
        self.assertTrue(math.isnan(result[32]))
        self.assertEqual(result[33:35], (math.inf, -math.inf))
        self.assertEqual(math.copysign(1.0, result[35]), -1.0)
        first = first_frame_from_conversion(
            (0.0,) * 64,
            iteration=0,
            bank32=0,
            bank31=0,
            bank53=0.0,
            bank54=0.0,
            bank60=0.0,
            bank59=values,
            array_to_cluster_return=converted + (0.0,) * 4,
        )
        self.assertTrue(math.isnan(first.vam[12]))
        self.assertEqual(math.copysign(1.0, first.vam[15]), -1.0)
        with self.assertRaises(ValueError):
            second_frame_from_conversions(
                (0.0,) * 64,
                bank62=0,
                bank66=values,
                bank67=(),
                bank66_array_to_cluster_return=converted[:3] + (0.0,),
                bank67_array_to_cluster_return=(0.0,) * 4,
            )
        with self.assertRaises(ValueError):
            second_frame_from_conversions(
                (0.0,) * 64,
                bank62=0,
                bank66=values,
                bank67=(),
                bank66_array_to_cluster_return=(0.0,) + converted[1:],
                bank67_array_to_cluster_return=(0.0,) * 4,
            )


if __name__ == "__main__":
    unittest.main()
