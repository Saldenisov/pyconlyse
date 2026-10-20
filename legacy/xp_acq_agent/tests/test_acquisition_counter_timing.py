"""Callback-only NI6602 request traces; runnable on actual Python 3.4."""

import unittest

from legacy.xp_acq_agent.elyse_agent.acquisition_counter_timing import (
    CALLER_FRAME_UIDS, CALLER_UIDS, HELPER_UIDS, PROPERTY_CODES,
    SOURCE_HELPER_SHA256, CounterTimingCancelled, CounterTimingError,
    decode_counter_bank, execute_counter_timing, labview_i32_to_u32_ticks,
    validate_counter_bank, project_counter_selector,
)


def bank(selector=1.0):
    return tuple(float(index) for index in range(32)) + (selector,)


class Harness(object):
    def __init__(self):
        self.image = bank()
        self.read_images = []
        self.trace = []
        self.observations = []
        self.done_values = [True]
        self.cancel = False
        self.on_record = None
        self.on_observe = None

    def record(self, name, *args):
        self.trace.append((name,) + args)
        if self.on_record is not None:
            self.on_record(name, args)

    def read(self):
        self.record("read")
        return self.read_images.pop(0) if self.read_images else self.image

    def write(self, image):
        self.record("write", image)
        self.image = image

    def publish(self, image):
        self.record("publish", image)

    def done(self, counter):
        self.record("done", counter)
        return self.done_values.pop(0) if len(self.done_values) > 1 else self.done_values[0]

    def stop(self, counter):
        self.record("stop", counter)

    def properties(self, counter, initial, low, high):
        self.record("properties", counter, initial, low, high)

    def start(self, counter):
        self.record("start", counter)

    def wait(self, seconds):
        self.record("wait", seconds)

    def cancelled(self):
        return self.cancel

    def observer(self, stage, uid):
        self.observations.append((stage, uid))
        if self.on_observe is not None:
            self.on_observe(stage, uid)

    def execute(self):
        return execute_counter_timing(self.read, self.write, self.publish,
                                      self.done, self.stop, self.properties,
                                      self.start, self.wait, self.cancelled,
                                      observer=self.observer)


class CounterTimingDecodeTests(unittest.TestCase):
    def test_exact_finite_immutable_float_bank_is_retained_without_coercion(self):
        image = bank()
        self.assertIs(validate_counter_bank(image), image)
        for image in (list(bank()), bank()[:-1], bank() + (0.0,),
                      (True,) + bank()[1:], (1,) + bank()[1:],
                      (float("nan"),) + bank()[1:],
                      bank()[:-1] + (float("inf"),)):
            with self.assertRaises(ValueError):
                validate_counter_bank(image)

    def test_all16_integer_selectors_map_to8_c10_pairs(self):
        for selector in range(1, 17):
            result = decode_counter_bank(bank(float(selector)))
            counter = (selector - 1) // 2
            self.assertEqual(result, {
                "selector": selector, "counter": counter,
                "delay_index": 2 * counter, "width_index": 2 * counter + 1,
                "delay_microseconds": float(2 * counter),
                "width_microseconds": float(2 * counter + 1),
                "delay_ticks": 40 * counter, "high_ticks": 40 * counter + 20,
            })

    def test_false_guard_is_not_a_c11_request(self):
        for selector in (-100.0, -1.0, 0.0, 17.0, 32.0, 100.0):
            self.assertIsNone(decode_counter_bank(bank(selector)))

    def test_source_admitted_invalid_task_is_not_python_negative_indexing(self):
        for selector in (5e-324, 0.1, 0.5, 0.9999999999999999):
            projection = project_counter_selector(selector)
            self.assertTrue(projection["source_guard"])
            self.assertEqual((projection["counter"], projection["delay_index"], projection["width_index"]),
                             (-1, -2, -1))
            self.assertFalse(projection["task_in_bounds"])
            self.assertFalse(projection["native_default_task_qualified"])
            with self.assertRaisesRegex(ValueError, "out-of-range"):
                decode_counter_bank(bank(selector))

    def test_fractions_follow_source_floor_before_i32_not_rounding_selector(self):
        for selector, q in ((1.0, 0), (1.5, 0), (2.5, 0), (2.9, 0),
                            (2.9999999999999996, 0), (3.0, 1), (3.5, 1),
                            (14.5, 6), (15.0, 7), (15.9, 7), (16.9, 7),
                            (16.999999999999996, 7)):
            decoded = decode_counter_bank(bank(selector))
            self.assertEqual(decoded["counter"], q)
            self.assertEqual((decoded["delay_index"], decoded["width_index"]), (2*q, 2*q+1))
            self.assertEqual(decoded["selector"], selector)
            self.assertIs(type(decoded["selector"]), float)

    def test_selector_projection_rejects_non_dbl_and_nonfinite_without_coercion(self):
        for selector in (True, 1, "1.5", float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                project_counter_selector(selector)

    def test_c11_fields_do_not_affect_selected_c10_pair(self):
        before = bank(16.0)
        after = before[:16] + (999.0,) * 16 + before[32:]
        self.assertEqual(decode_counter_bank(before), decode_counter_bank(after))

    def test_source_i32_ties_even_saturation_then_unsigned_bits(self):
        rows = ((0.0, 0), (0.025, 0), (0.075, 2), (0.125, 2),
                (0.16, 3), (-0.025, 0), (-0.075, 4294967294),
                (-0.05, 4294967295), (2147483648 / 20.0, 2147483647),
                (-2147483649 / 20.0, 2147483648))
        for value, expected in rows:
            self.assertEqual(labview_i32_to_u32_ticks(value), expected)

    def test_nonfinite_products_and_coercible_values_rejected_before_io(self):
        for value in (True, "1", None, float("nan"), float("inf"),
                      -float("inf"), 1e308, 10 ** 1000):
            with self.assertRaises(ValueError):
                labview_i32_to_u32_ticks(value)


class CounterTimingTraceTests(unittest.TestCase):
    def test_done_first_iteration_has_exact_callback_order_and_source_anchors(self):
        h = Harness()
        before = h.image
        result = h.execute()
        reset = before[:32] + (-1.0,)
        self.assertEqual(h.trace, [
            ("read",), ("done", 0), ("wait", 0.001), ("stop", 0),
            ("properties", 0, 0, 0, 20), ("start", 0),
            ("read",), ("write", reset), ("read",), ("publish", reset),
        ])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["source_frames_completed"], [0, 1, 2])
        self.assertEqual(result["caller_frame_uids"], ["23641", "22979", "1507"])
        self.assertEqual(CALLER_FRAME_UIDS, ("23641", "22979", "1507"))
        self.assertEqual(HELPER_UIDS, ("3202", "3194", "2976", "309", "3083", "3032"))
        self.assertEqual(PROPERTY_CODES, (664, 4465, 4457))
        self.assertEqual(SOURCE_HELPER_SHA256,
                         "4DB9022F837C5629DE670347D00C39285ACEAA61FE7CCA592D99D6F67713E211")
        self.assertEqual(result["pending_counter_stops"], [])
        self.assertEqual(result["commanded_running_counters"], [0])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertTrue(result["ownership_retained_by_caller"])
        self.assertFalse(result["source_error_semantics_reproduced"])
        self.assertFalse(result["native_timing_equivalence"])
        self.assertFalse(result["atomic_snapshot"])
        self.assertFalse(result["automatic_retry"])

    def test_all16_commands_use_existing_counter_number_and_expected_ticks(self):
        for selector in range(1, 17):
            h = Harness()
            h.image = bank(float(selector))
            h.execute()
            counter = (selector - 1) // 2
            self.assertIn(("properties", counter, 40 * counter,
                           40 * counter, 40 * counter + 20), h.trace)
            self.assertEqual([row for row in h.trace if row[0] == "start"],
                             [("start", counter)])

    def test_not_done_exits_at_i21_with22_reads_and22_waits(self):
        h = Harness()
        h.done_values = [False]
        result = h.execute()
        self.assertEqual(result["poll_iterations"], 22)
        self.assertEqual(result["poll_exit_reason"], "iteration_limit")
        self.assertEqual(result["polls"], [(i, False) for i in range(22)])
        self.assertEqual(h.trace.count(("done", 0)), 22)
        self.assertEqual(h.trace.count(("wait", 0.001)), 22)
        self.assertAlmostEqual(result["requested_wait_seconds"], 0.022)

    def test_done_on_later_iteration_still_waits_after_final_read(self):
        h = Harness()
        h.done_values = [False, False, True]
        result = h.execute()
        self.assertEqual(result["poll_iterations"], 3)
        self.assertEqual(result["poll_exit_reason"], "pulse_done")
        self.assertEqual(h.trace[1:8], [
            ("done", 0), ("wait", 0.001), ("done", 0), ("wait", 0.001),
            ("done", 0), ("wait", 0.001), ("stop", 0)])

    def test_false_source_arm_has_one_read_no_reset_publish_or_counter_io(self):
        for selector in (-1.0, 0.0, 17.0, 32.0):
            h = Harness()
            h.image = bank(selector)
            result = h.execute()
            self.assertEqual(h.trace, [("read",)])
            self.assertEqual(result["status"], "NO_REQUEST")
            self.assertEqual(result["source_frames_completed"], [])

    def test_three_reads_are_independent_not_reuse_of_dispatch_or_reset_image(self):
        h = Harness()
        dispatch = bank(7.0)
        reset = tuple(float(i + 100) for i in range(32)) + (16.0,)
        publication = tuple(float(i + 200) for i in range(32)) + (10.0,)
        h.read_images = [dispatch, reset, publication]
        result = h.execute()
        self.assertIn(("properties", 3, 120, 120, 140), h.trace)
        self.assertIn(("write", reset[:32] + (-1.0,)), h.trace)
        self.assertEqual(h.trace[-1], ("publish", publication))
        self.assertEqual(result["dispatch_snapshot"], dispatch)
        self.assertEqual(result["reset_snapshot"], reset)
        self.assertEqual(result["publication_snapshot"], publication)

    def test_observer_contains_original_callsite_uids(self):
        h = Harness()
        h.execute()
        for name in ("dispatch_read", "reset_read", "selector_reset",
                     "publication_read", "publication",
                     "simple_error_handler_boundary"):
            self.assertIn((name, CALLER_UIDS[name]), h.observations)
        self.assertIn(("pulse_done", "3202"), h.observations)
        self.assertIn(("poll_wait", "3194"), h.observations)
        self.assertIn(("write_timing_properties", "3083"), h.observations)

    def test_negative_and_saturated_source_ticks_pass_as_bits_not_driver_permit(self):
        h = Harness()
        h.image = (-0.05, 2147483648 / 20.0) + h.image[2:]
        h.execute()
        self.assertIn(("properties", 0, 4294967295, 4294967295, 2147483647), h.trace)


class CounterTimingFailureTests(unittest.TestCase):
    def fail_at(self, name):
        h = Harness()
        def fail(current, args):
            if current == name:
                raise RuntimeError("ambiguous " + name)
        h.on_record = fail
        return h

    def get_failure(self, h, kind=CounterTimingError):
        with self.assertRaises(kind) as raised:
            h.execute()
        result = raised.exception.report
        self.assertIs(raised.exception.result, result)
        self.assertFalse(result["completed"])
        self.assertTrue(result["ownership_retained_by_caller"])
        self.assertFalse(result["hardware_acknowledged"])
        return result

    def test_invalid_task_selector_fails_before_any_counter_or_consumption(self):
        h = Harness()
        h.image = bank(.5)
        result = self.get_failure(h)
        self.assertEqual(h.trace, [("read",)])
        self.assertFalse(result["stop_attempted"])
        self.assertFalse(result["selector_reset_attempted"])

    def test_bad_read_image_fails_before_counter_io(self):
        for image in (bank()[:-1], (1,) + bank()[1:],
                      (float("nan"),) + bank()[1:]):
            h = Harness()
            h.image = image
            self.get_failure(h)
            self.assertEqual(h.trace, [("read",)])

    def test_non_boolean_done_is_not_coerced_or_treated_as_completion(self):
        for value in (None, 0, 1, "True", (True,)):
            h = Harness()
            h.done_values = [value]
            result = self.get_failure(h)
            self.assertEqual(h.trace, [("read",), ("done", 0)])
            self.assertFalse(result["stop_attempted"])

    def test_poll_exception_does_not_fabricate_false_and_continue(self):
        h = self.fail_at("done")
        result = self.get_failure(h)
        self.assertEqual(h.trace, [("read",), ("done", 0)])
        self.assertEqual(result["poll_iterations"], 0)
        self.assertFalse(result["clear_errors_boundary_reached"])

    def test_stop_failure_is_uncertain_no_clear_configure_restart_or_auto_retry(self):
        h = self.fail_at("stop")
        result = self.get_failure(h)
        self.assertEqual(h.trace[-1], ("stop", 0))
        self.assertEqual(h.trace.count(("stop", 0)), 1)
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertFalse(result["stop_completed"])
        self.assertFalse(result["clear_errors_boundary_reached"])
        self.assertFalse(result["configuration_attempted"])

    def test_property_failure_keeps_uncertainty_and_confirmed_stopped_counter(self):
        h = self.fail_at("properties")
        result = self.get_failure(h)
        self.assertTrue(result["stop_completed"])
        self.assertTrue(result["clear_errors_boundary_reached"])
        self.assertTrue(result["configuration_attempted"])
        self.assertTrue(result["configuration_uncertain"])
        self.assertFalse(result["configuration_completed"])
        self.assertFalse(result["start_attempted"])
        self.assertEqual(result["pending_counter_stops"], [])
        self.assertEqual(h.trace[-1], ("properties", 0, 0, 0, 20))

    def test_start_exception_keeps_counter_pending_without_automatic_stop(self):
        h = self.fail_at("start")
        result = self.get_failure(h)
        self.assertTrue(result["configuration_completed"])
        self.assertFalse(result["configuration_uncertain"])
        self.assertTrue(result["start_attempted"])
        self.assertFalse(result["start_completed"])
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertEqual(h.trace.count(("stop", 0)), 1)
        self.assertEqual(h.trace[-1], ("start", 0))
        self.assertFalse(result["selector_reset_attempted"])

    def test_selector_reset_failure_retains_uncertain_image_and_running_owner(self):
        h = self.fail_at("write")
        result = self.get_failure(h)
        self.assertEqual(result["source_frames_completed"], [0])
        self.assertTrue(result["start_completed"])
        self.assertTrue(result["selector_reset_attempted"])
        self.assertTrue(result["selector_reset_uncertain"])
        self.assertFalse(result["selector_reset_completed"])
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertFalse(result["publication_attempted"])

    def test_publication_failure_not_replayed_after_consuming_selector(self):
        h = self.fail_at("publish")
        result = self.get_failure(h)
        self.assertEqual(result["source_frames_completed"], [0, 1])
        self.assertTrue(result["selector_reset_completed"])
        self.assertTrue(result["publication_uncertain"])
        self.assertFalse(result["publication_completed"])
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertEqual(len([row for row in h.trace if row[0] == "publish"]), 1)

    def test_reset_read_validation_failure_keeps_running_counter_owned(self):
        h = Harness()
        h.read_images = [bank(), bank()[:-1]]
        result = self.get_failure(h)
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertTrue(result["start_completed"])
        self.assertFalse(result["selector_reset_attempted"])

    def test_callback_raised_public_error_cannot_replace_this_invocations_report(self):
        h = Harness()
        foreign = {"operation": "foreign", "status": "FAILED"}
        def fail(name, args):
            if name == "properties":
                raise CounterTimingCancelled(foreign)
        h.on_record = fail
        result = self.get_failure(h)
        self.assertEqual(result["status"], "FAILED")
        self.assertTrue(result["configuration_uncertain"])
        self.assertIsNot(result, foreign)

    def test_static_callback_shape_rejected_before_any_callback(self):
        h = Harness()
        with self.assertRaises(TypeError):
            execute_counter_timing(h.read, h.write, h.publish, None, h.stop,
                                   h.properties, h.start, h.wait, h.cancelled)
        self.assertEqual(h.trace, [])


class CounterTimingCancellationTests(unittest.TestCase):
    def test_preexisting_cancel_has_no_bank_or_counter_effect(self):
        h = Harness()
        h.cancel = True
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        self.assertEqual(h.trace, [])
        self.assertEqual(raised.exception.report["pending_counter_stops"], [])

    def test_cancel_in_wait_never_stops_or_reconfigures_counter(self):
        h = Harness()
        def cancel(name, args):
            if name == "wait":
                h.cancel = True
        h.on_record = cancel
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        self.assertEqual(h.trace, [("read",), ("done", 0), ("wait", 0.001)])
        self.assertEqual(raised.exception.report["poll_iterations"], 1)
        self.assertFalse(raised.exception.report["stop_attempted"])

    def test_cancel_after_confirmed_stop_prevents_configuration_and_restart(self):
        h = Harness()
        def cancel(name, args):
            if name == "stop":
                h.cancel = True
        h.on_record = cancel
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        result = raised.exception.report
        self.assertTrue(result["stop_completed"])
        self.assertEqual(result["pending_counter_stops"], [])
        self.assertFalse(result["configuration_attempted"])
        self.assertEqual(h.trace[-1], ("stop", 0))

    def test_cancel_after_successful_configuration_does_not_start_or_rollback(self):
        h = Harness()
        def cancel(name, args):
            if name == "properties":
                h.cancel = True
        h.on_record = cancel
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        result = raised.exception.report
        self.assertTrue(result["configuration_completed"])
        self.assertFalse(result["configuration_uncertain"])
        self.assertFalse(result["start_attempted"])
        self.assertEqual(h.trace[-1], ("properties", 0, 0, 0, 20))

    def test_cancel_after_successful_start_retains_pending_stop_and_no_consumption(self):
        h = Harness()
        def cancel(name, args):
            if name == "start":
                h.cancel = True
        h.on_record = cancel
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        result = raised.exception.report
        self.assertTrue(result["start_completed"])
        self.assertEqual(result["commanded_running_counters"], [0])
        self.assertEqual(result["pending_counter_stops"], [0])
        self.assertFalse(result["selector_reset_attempted"])
        self.assertEqual(h.trace.count(("stop", 0)), 1)

    def test_cancel_after_publication_keeps_completed_effects_not_false_failure(self):
        h = Harness()
        def cancel(name, args):
            if name == "publish":
                h.cancel = True
        h.on_record = cancel
        with self.assertRaises(CounterTimingCancelled) as raised:
            h.execute()
        result = raised.exception.report
        self.assertEqual(result["source_frames_completed"], [0, 1, 2])
        self.assertTrue(result["publication_completed"])
        self.assertFalse(result["publication_uncertain"])
        self.assertEqual(result["pending_counter_stops"], [0])

    def test_observer_failure_is_fail_closed_and_does_not_restart(self):
        h = Harness()
        def fail(stage, uid):
            if stage == "clear_errors_boundary":
                raise RuntimeError("observer refused")
        h.on_observe = fail
        with self.assertRaises(CounterTimingError) as raised:
            h.execute()
        self.assertEqual(h.trace[-1], ("stop", 0))
        self.assertFalse(raised.exception.report["configuration_attempted"])

    def test_nonboolean_cancellation_rejected_without_callbacks(self):
        h = Harness()
        h.cancel = 1
        with self.assertRaises(CounterTimingError) as raised:
            h.execute()
        self.assertEqual(h.trace, [])
        self.assertEqual(raised.exception.report["failures"][0]["error_type"], "TypeError")


if __name__ == "__main__":
    unittest.main()
