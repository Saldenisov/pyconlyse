"""Golden caller traces distinguish offset, cases, supplied means and errors."""

import math
import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    UNSUPPLIED,
    ErrorCluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.ni6220_runtime import (
    completed_iteration,
    counter_frame,
    point_frame,
)


class Ni6220RuntimeProjectionTests(unittest.TestCase):
    def arguments(self, *, selector=0, current=1.0, previous=1.0):
        return dict(
            reader_values=tuple(float(i) for i in range(16)),
            bank65=(10.0, 11.0, 12.0, 13.0),
            bank66=(20.0,) * 4,
            bank67=(30.0,) * 4,
            current_mean_return=current,
            previous_mean_return=previous,
            counter_selector_snapshot=selector,
            increment_read_snapshot=9,
            increment_return=10,
        )

    def point_arguments(self):
        return dict(
            reader_values=tuple(float(i) for i in range(16)),
            point_mean_returns=(100.0, 101.0, 102.0, 103.0, 108.0, 109.0),
            bank63=4,
        )

    def test_equal_offset_is_false_not_greater_equal(self):
        result = counter_frame(**self.arguments(current=1.03, previous=1.0))
        self.assertFalse(result.threshold_true)
        self.assertFalse(result.counter_written)
        self.assertEqual(result.counter_after, 0)
        self.assertEqual(result.bank65_previous, (4.0, 5.0, 6.0, 7.0))
        self.assertEqual(result.bank67_before_rise, (30.0,) * 4)

    def test_threshold_is_relative_to_previous_not_absolute(self):
        self.assertFalse(
            counter_frame(
                **self.arguments(current=100.01, previous=100.0)
            ).threshold_true
        )
        self.assertTrue(
            counter_frame(
                **self.arguments(current=-99.9, previous=-100.0)
            ).threshold_true
        )

    def test_false_zero_does_not_start_collection(self):
        result = counter_frame(**self.arguments(selector=0))
        self.assertEqual(result.counter_diagram_uid, "104729")
        self.assertEqual(result.bank66_captured, (20.0,) * 4)

    def test_true_zero_starts_and_saves_old_baseline(self):
        result = counter_frame(**self.arguments(current=2.0))
        self.assertEqual(result.counter_after, 10)
        self.assertEqual(result.bank67_before_rise, (10.0, 11.0, 12.0, 13.0))
        self.assertEqual(result.counter_diagram_uid, "81862")

    def test_false_one_two_and_default_use_supplied_later_increment_return(self):
        for selector in (1, 2, 4, 2**32 - 1):
            result = counter_frame(**self.arguments(selector=selector))
            self.assertEqual(result.counter_after, 10)
            self.assertEqual(result.counter_diagram_uid, "100537")
            self.assertFalse(result.captured)

    def test_three_in_both_arms_captures_same_current_bank66_then_resets(self):
        for current, uid in ((1.0, "100569"), (2.0, "81868")):
            result = counter_frame(**self.arguments(selector=3, current=current))
            self.assertEqual(result.counter_after, 0)
            self.assertEqual(result.bank66_captured, (4.0, 5.0, 6.0, 7.0))
            self.assertEqual(result.counter_diagram_uid, uid)

    def test_true_nonexplicit_selectors_remain_unknown(self):
        for selector in (1, 2, 4, 2**32 - 1):
            result = counter_frame(**self.arguments(selector=selector, current=2.0))
            self.assertIs(result.counter_after, UNSUPPLIED)
            self.assertIs(result.bank66_captured, UNSUPPLIED)
            self.assertIs(result.captured, UNSUPPLIED)
            self.assertEqual(result.bank67_before_rise, (10.0, 11.0, 12.0, 13.0))

    def test_six_means_have_distinct_calls_channel_order_and_length20(self):
        result = point_frame(**self.point_arguments())
        self.assertEqual(len(result.bank59), 6)
        self.assertEqual(tuple(c.channel for c in result.calls), (0, 1, 2, 3, 8, 9))
        self.assertEqual(
            tuple(c.input_value for c in result.calls), (0.0, 1.0, 2.0, 3.0, 8.0, 9.0)
        )
        self.assertEqual(len({c.node_uid for c in result.calls}), 6)
        self.assertEqual({c.sample_length for c in result.calls}, {20})
        self.assertEqual(result.indicator, 108.0)

    def test_out_of_range_dbl_indicator_has_documented_type_default(self):
        args = self.point_arguments()
        for index in range(2**16):
            args["bank63"] = index
            expected = args["point_mean_returns"][index] if index < 6 else 0.0
            actual = point_frame(**args).indicator
            self.assertIs(type(actual), float)
            self.assertEqual(actual, expected)

    def test_read_error_does_not_gate_data_or_create_same_iteration_stop(self):
        fault = ErrorCluster(True, -99, "fixture read failure")
        result = completed_iteration(
            read_error=fault,
            stop_snapshot=False,
            point_arguments=self.point_arguments(),
            counter_arguments=self.arguments(),
        )
        self.assertEqual(result.handler_error, fault)
        self.assertEqual(len(result.point_frame.bank59), 6)
        self.assertTrue(result.keep_running)
        self.assertEqual(result.requested_wait_ms, 15)
        result = completed_iteration(
            read_error=fault,
            stop_snapshot=True,
            point_arguments=self.point_arguments(),
            counter_arguments=self.arguments(),
        )
        self.assertFalse(result.keep_running)

    def test_short_arrays_use_element_defaults_not_slice_truncation(self):
        for length in range(17):
            values = tuple(float(i + 100) for i in range(length))
            counter_args, point_args = self.arguments(), self.point_arguments()
            counter_args["reader_values"] = point_args["reader_values"] = values
            counter_args["counter_selector_snapshot"] = 3
            result = counter_frame(**counter_args)
            expected = tuple(values[i] if i < length else 0.0 for i in (4, 5, 6, 7))
            self.assertEqual(result.bank65_previous, expected)
            self.assertEqual(result.bank66_captured, expected)
            self.assertEqual(result.bank67_before_rise, (30.0,) * 4)
            points = point_frame(**point_args)
            self.assertEqual(
                tuple(call.input_value for call in points.calls),
                tuple(values[i] if i < length else 0.0 for i in (0, 1, 2, 3, 8, 9)),
            )
            self.assertEqual(points.bank59, point_args["point_mean_returns"])

    def test_empty_read_with_error_still_enters_data_frames(self):
        counter_args, point_args = self.arguments(), self.point_arguments()
        counter_args["reader_values"] = point_args["reader_values"] = ()
        counter_args["counter_selector_snapshot"] = 3
        result = completed_iteration(
            read_error=ErrorCluster(True, -99, "explicit failed-read fixture"),
            stop_snapshot=False,
            counter_arguments=counter_args,
            point_arguments=point_args,
        )
        self.assertEqual(result.counter_frame.bank66_captured, (0.0,) * 4)
        self.assertEqual(
            tuple(call.input_value for call in result.point_frame.calls), (0.0,) * 6
        )
        self.assertTrue(result.keep_running)
        self.assertTrue(result.handler_error.status)
        self.assertEqual(result.point_frame.bank59, point_args["point_mean_returns"])

    def test_indexed_nonfinite_values_and_signed_zero_are_not_sanitized(self):
        values = (math.nan, math.inf, -math.inf, -0.0) * 4
        counter_args, point_args = self.arguments(), self.point_arguments()
        counter_args["reader_values"] = point_args["reader_values"] = values
        result = counter_frame(**counter_args)
        self.assertTrue(math.isnan(result.bank65_previous[0]))
        self.assertEqual(result.bank65_previous[1:3], (math.inf, -math.inf))
        self.assertEqual(math.copysign(1.0, result.bank65_previous[3]), -1.0)
        points = point_frame(**point_args)
        self.assertTrue(math.isnan(points.calls[0].input_value))
        self.assertTrue(math.isnan(points.calls[4].input_value))
        self.assertEqual(math.copysign(1.0, points.calls[3].input_value), -1.0)

    def test_fixture_bounds_still_reject_untyped_arrays_and_signed_counter(self):
        args = self.arguments()
        for values in ([1.0], (True,), (1,), ("0.0",)):
            args["reader_values"] = values
            with self.assertRaises(TypeError):
                counter_frame(**args)
        for bank in ("bank65", "bank66", "bank67"):
            for values in ([1.0], (True,), (1,), ("0.0",)):
                args = self.arguments()
                args[bank] = values
                with self.assertRaises(TypeError):
                    counter_frame(**args)
        args = self.arguments(selector=-1)
        with self.assertRaises(ValueError):
            counter_frame(**args)
        for index in (-1, 2**16, True, 1.0):
            points = self.point_arguments()
            points["bank63"] = index
            with self.assertRaises(ValueError):
                point_frame(**points)


if __name__ == "__main__":
    unittest.main()
