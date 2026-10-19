import unittest

from supervision_reconstruction.domain.ni6602 import (
    COUNTER_INITIALIZATION_PLAN,
    I32_MAX,
    I32_MIN,
    legacy_value_to_ticks,
    make_pulse_update_plan,
    microseconds_to_ticks,
)


class Ni6602Tests(unittest.TestCase):
    def test_initialization_plan_preserves_all_eight_wired_counter_constants(self) -> None:
        self.assertEqual(
            [item.counter for item in COUNTER_INITIALIZATION_PLAN],
            [
                "Dev1/ctr0",
                "Dev1/ctr1",
                "Dev1/ctr2",
                "Dev1/ctr3",
                "Dev1/ctr4",
                "Dev1/ctr5",
                "Dev1/ctr6",
                "Dev1/ctr7",
            ],
        )
        self.assertEqual(
            [
                (item.initial_delay_ticks, item.low_ticks, item.high_ticks)
                for item in COUNTER_INITIALIZATION_PLAN
            ],
            [
                (0, 7, 7),
                (0, 43520, 2000),
                (0, 40166, 200),
                (0, 43500, 200),
                (0, 43500, 2000),
                (0, 10000, 10000),
                (0, 6, 200),
                (0, 43500, 2000),
            ],
        )
        self.assertTrue(
            all(item.retriggerable and item.finite_samples == 1 for item in COUNTER_INITIALIZATION_PLAN)
        )
        self.assertTrue(
            all(item.trigger_source == "/Dev1/PFI10" for item in COUNTER_INITIALIZATION_PLAN)
        )
        self.assertTrue(
            all(item.counter_timebase_source == "/Dev1/PFI11" for item in COUNTER_INITIALIZATION_PLAN)
        )
        self.assertTrue(
            all(item.trigger_edge == "rising" for item in COUNTER_INITIALIZATION_PLAN)
        )
        self.assertTrue(
            all(item.counter_timebase_rate_hz is None for item in COUNTER_INITIALIZATION_PLAN)
        )
        self.assertTrue(
            all(
                item.counter_timebase_active_edge == "rising"
                for item in COUNTER_INITIALIZATION_PLAN
            )
        )
        self.assertTrue(all(item.idle_state == "low" for item in COUNTER_INITIALIZATION_PLAN))

    def test_runtime_write_plan_is_hardware_free_and_preserves_stop_write_start_order(self) -> None:
        plan = make_pulse_update_plan(delay_value=12.5, width_value=3.0)

        self.assertEqual(plan.initial_delay_ticks, 250)
        self.assertEqual(plan.low_ticks, 250)
        self.assertEqual(plan.high_ticks, 60)
        self.assertEqual(plan.poll_interval_ms, 1)
        self.assertEqual(
            plan.ordering,
            (
                "wait_until_pulse_done",
                "stop_task",
                "write_initial_delay",
                "write_low_ticks",
                "write_high_ticks",
                "start_task",
            ),
        )

    def test_legacy_conversion_policy_uses_factor_twenty_and_nearest_even_ties(self) -> None:
        self.assertEqual(legacy_value_to_ticks(0.0), 0)
        self.assertEqual(legacy_value_to_ticks(1.0), 20)
        self.assertEqual(legacy_value_to_ticks(1.25), 25)
        self.assertEqual(legacy_value_to_ticks(0.025), 0)
        self.assertEqual(legacy_value_to_ticks(0.075), 2)
        self.assertEqual(legacy_value_to_ticks(-0.025), 0)
        self.assertEqual(legacy_value_to_ticks(-0.075), -2)

    def test_legacy_conversion_policy_saturates_i32_and_rejects_nonfinite_values(self) -> None:
        self.assertEqual(legacy_value_to_ticks((I32_MAX - 0.49) / 20), I32_MAX)
        self.assertEqual(legacy_value_to_ticks((I32_MAX + 0.51) / 20), I32_MAX)
        self.assertEqual(legacy_value_to_ticks((I32_MIN + 0.49) / 20), I32_MIN)
        self.assertEqual(legacy_value_to_ticks((I32_MIN - 0.51) / 20), I32_MIN)
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaisesRegex(ValueError, "finite"):
                legacy_value_to_ticks(value)
        with self.assertRaisesRegex(ValueError, "non-boolean"):
            legacy_value_to_ticks(True)

    def test_old_microseconds_name_is_neutral_compatibility_alias(self) -> None:
        self.assertEqual(microseconds_to_ticks(1.25), legacy_value_to_ticks(1.25))
