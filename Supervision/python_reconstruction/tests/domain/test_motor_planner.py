import unittest

from supervision_reconstruction.domain.motor_planner import (
    Axis,
    Direction,
    decide_motion_termination,
    legacy_default_motor_pair_for_laser,
    motor_pair_for_laser,
    plan_relative_move,
)


class MotorPlannerTests(unittest.TestCase):
    def test_laser_selector_cases_match_evidenced_pairs(self) -> None:
        self.assertEqual(motor_pair_for_laser(1).x_motor, 3)
        self.assertEqual(motor_pair_for_laser(1).y_motor, 4)
        self.assertEqual(motor_pair_for_laser(2).x_motor, 1)
        self.assertEqual(motor_pair_for_laser(2).y_motor, 2)
        with self.assertRaisesRegex(ValueError, "exactly 1 or 2"):
            motor_pair_for_laser(99)
        with self.assertRaisesRegex(ValueError, "exactly 1 or 2"):
            motor_pair_for_laser(1.0)
        self.assertEqual(legacy_default_motor_pair_for_laser(99).x_motor, 1)
        self.assertEqual(legacy_default_motor_pair_for_laser(99).y_motor, 2)

    def test_one_hot_button_masks_plan_correct_axis_motor_and_signed_steps(self) -> None:
        expected = {
            1: (Axis.X, Direction.FORWARD, 0, 3, 5),
            2: (Axis.X, Direction.REVERSE, 0, 3, -5),
            4: (Axis.Y, Direction.FORWARD, 1, 4, 5),
            8: (Axis.Y, Direction.REVERSE, 1, 4, -5),
        }
        for mask, (axis, direction, index, motor, steps) in expected.items():
            plan = plan_relative_move(1, mask, 5)
            self.assertEqual(
                (plan.axis, plan.direction, plan.motor_index, plan.motor_number, plan.signed_steps),
                (axis, direction, index, motor, steps),
            )

    def test_zero_multiple_and_unknown_masks_fail_closed(self) -> None:
        for mask in (0, 3, 5, 15, 16):
            with self.assertRaisesRegex(ValueError, "fail closed"):
                plan_relative_move(1, mask, 5)
        with self.assertRaisesRegex(ValueError, "one-hot mask"):
            plan_relative_move(1, 1.0, 5)
        with self.assertRaisesRegex(ValueError, "I32 non-negative"):
            plan_relative_move(1, 1, -1)
        with self.assertRaisesRegex(ValueError, "I32 non-negative"):
            plan_relative_move(1, 1, 2**31)
        with self.assertRaisesRegex(ValueError, "integer magnitude"):
            plan_relative_move(1, 1, True)
        with self.assertRaisesRegex(ValueError, "exactly 1 or 2"):
            plan_relative_move(3, 1, 1)

    def test_termination_and_abort_decision_match_observed_or_chain(self) -> None:
        for motion_done in (False, True):
            for error_status in (False, True):
                for stop_motor in (False, True):
                    decision = decide_motion_termination(
                        motion_done=motion_done,
                        error_status=error_status,
                        stop_motor=stop_motor,
                    )
                    self.assertEqual(
                        decision.terminate,
                        motion_done or error_status or stop_motor,
                    )
                    self.assertEqual(decision.abort_requested, stop_motor)
