"""Pure beam-line adjustment fixtures; no real UI or card state is accessed."""

import math
import unittest

from DeviceServers.control.elyse_acq.vi_simulation.beamline_adjustment import (
    BUTTONS,
    UnverifiedOuterDefaultError,
    adjust_setpoint,
    adjustment_parameters,
    project_frame0,
    select_change,
)

CELL = (False, False, False, False, False, 0.0, 0.0, False, False, False, False)


def replace(cell, **fields):
    value = list(cell)
    for field, item in fields.items():
        value[int(field[1:])] = item
    return tuple(value)


class BeamlineAdjustmentTests(unittest.TestCase):
    def test_mask_ignores_setpoint_readback_and_status_changes(self):
        old = (CELL,) * 11
        new = (replace(CELL, f1=True, f2=True, f3=True, f5=99.0, f6=-12.0),) * 11
        selected = select_change(1, old, new)
        self.assertEqual(selected.masked_changes, (0,) * 11)
        self.assertEqual(
            (selected.maximum, selected.selected_index, selected.apply_setpoints),
            (0, 0, False),
        )

    def test_numeric_max_and_first_tie_are_not_global_or(self):
        old = (CELL,) * 11
        new = list(old)
        new[0] = replace(CELL, f7=True)
        new[3] = replace(CELL, f10=True)
        new[5] = replace(CELL, f10=True)
        selected = select_change(1, old, tuple(new))
        self.assertEqual((selected.maximum, selected.selected_index), (1024, 3))
        self.assertTrue(selected.apply_setpoints)

    def test_button_release_is_a_difference_too(self):
        old = (replace(CELL, f8=True),) + (CELL,) * 8
        selected = select_change(2, old, (CELL,) * 9)
        self.assertEqual(selected.maximum, 256)

    def test_simultaneous_fields_do_not_receive_invented_outer_default(self):
        old = (CELL,) * 9
        new = (replace(CELL, f0=True, f7=True),) + old[1:]
        self.assertEqual(select_change(2, old, new).maximum, 129)
        with self.assertRaises(UnverifiedOuterDefaultError):
            project_frame0(2, old_cells=old, new_cells=new, current_selected_cell=CELL)

    def test_current_property_snapshot_not_newval_controls_adjustment(self):
        old = (CELL,) * 11
        new = list(old)
        new[1] = replace(CELL, f9=True, f5=50.0)
        current = (True, True, False, True, True, 20.0, -3.0, True, True, True, True)
        selected, plan = project_frame0(
            1, old_cells=old, new_cells=tuple(new), current_selected_cell=current
        )
        self.assertEqual(selected.selected_index, 1)
        self.assertEqual(
            plan.value, current[:5] + (21.0,) + current[6:7] + (False,) * 4
        )
        self.assertEqual((plan.wait_request_ms, plan.property_name), (70, "Value"))
        self.assertEqual(current[5], 20.0)

    def test_explicit_nonbutton_cases_pass_seven_fields_and_reset_buttons(self):
        for field in (None, 0, 4):
            old = (CELL,) * 9
            new = (
                old
                if field is None
                else (replace(CELL, **{f"f{field}": True}),) + old[1:]
            )
            current = replace(CELL, f5=-0.0, f6=27.0, f7=True, f9=True)
            selected, plan = project_frame0(
                2, old_cells=old, new_cells=new, current_selected_cell=current
            )
            self.assertFalse(selected.apply_setpoints)
            self.assertEqual(plan.value[:7], current[:7])
            self.assertEqual(plan.value[5].hex(), "-0x0.0p+0")
            self.assertEqual(plan.value[7:], (False,) * 4)

    def test_all_step_groups_directions_and_both_scale_modes(self):
        groups = {
            1: (
                ((1,), 0.0, 120.0, (1.0, 10.0), (0.1, 1.0)),
                ((2,), 0.0, 180.0, (5.0, 50.0), (1.0, 5.0)),
                ((0, 7, 8), -16.0, 16.0, (0.1, 1.0), (0.01, 0.1)),
                ((3, 4, 5, 6, 9, 10), -5.0, 5.0, (0.1, 1.0), (0.01, 0.1)),
            ),
            2: (
                ((0, 1, 2, 3, 6), -16.0, 16.0, (0.1, 1.0), (0.01, 0.1)),
                ((4, 5, 7, 8), -5.0, 5.0, (0.1, 1.0), (0.01, 0.1)),
            ),
        }
        for event, rows in groups.items():
            for indices, lower, upper, coarse, fine in rows:
                for index in indices:
                    for button in BUTTONS:
                        small, large = coarse if button in (128, 1024) else fine
                        self.assertEqual(
                            adjustment_parameters(event, index, button),
                            (small, large, lower, upper),
                        )
                        current = 80.0 if lower == 0.0 else 0.0
                        for scale, step in ((False, small), (True, large)):
                            expected = (
                                current - step
                                if button in (128, 256)
                                else current + step
                            )
                            self.assertEqual(
                                adjust_setpoint(event, index, button, current, scale),
                                expected,
                            )

    def test_saved_nested_defaults_pass_without_clipping(self):
        for event, indices in ((1, (-1, 11, 100)), (2, (-1, 9, 10, 11, 100))):
            for index in indices:
                for button in BUTTONS:
                    self.assertIsNone(adjustment_parameters(event, index, button))
                    self.assertEqual(
                        adjust_setpoint(event, index, button, 1000.0, True), 1000.0
                    )

    def test_coercion_bounds_apply_even_for_already_overrange_current_values(self):
        for current, expected in ((-100.0, -16.0), (100.0, 16.0)):
            for button in BUTTONS:
                self.assertEqual(
                    adjust_setpoint(2, 0, button, current, False), expected
                )

    def test_invalid_schema_and_nonfinite_values_are_not_guessed(self):
        for value in (math.nan, math.inf, -math.inf):
            with self.assertRaises(ValueError):
                select_change(1, (replace(CELL, f5=value),) * 11, (CELL,) * 11)
        for malformed in ((CELL,) * 9, [CELL] * 11, (replace(CELL, f5=0),) * 11):
            with self.assertRaises(TypeError):
                select_change(1, malformed, (CELL,) * 11)
        for event in (True, 3, "1"):
            with self.assertRaises(ValueError):
                select_change(event, (CELL,) * 11, (CELL,) * 11)


if __name__ == "__main__":
    unittest.main()
