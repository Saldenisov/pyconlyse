import unittest

from supervision_reconstruction.domain.font_ui import (
    FONT_METRICS_BLOCKED,
    SET_BOLD_TEXT_BLOCKED,
    PropertyNodeFont,
    TextRect,
    convert_property_node_font_to_graphics_font,
    longest_line_width_from_rectangles,
    plan_set_bold_text,
)


class FontUiTests(unittest.TestCase):
    def test_font_cluster_remap_discards_color_and_forces_outline_shadow_false(self) -> None:
        source = PropertyNodeFont("Arial", 12, True, False, True, True, 0x00FF00)
        result = convert_property_node_font_to_graphics_font(source)
        self.assertEqual(result.font_name, "Arial")
        self.assertEqual(result.size, 12)
        self.assertTrue(result.bold)
        self.assertTrue(result.underline)
        self.assertTrue(result.strikeout)
        self.assertFalse(result.outline)
        self.assertFalse(result.shadow)
        with self.assertRaises(TypeError):
            convert_property_node_font_to_graphics_font(
                PropertyNodeFont("Arial", -1, False, False, False, False, 0)
            )
        with self.assertRaises(TypeError):
            convert_property_node_font_to_graphics_font(
                PropertyNodeFont("Arial", 1, False, False, False, False, -1)
            )
        with self.assertRaises(OverflowError):
            convert_property_node_font_to_graphics_font(
                PropertyNodeFont("Arial", 32768, False, False, False, False, 0)
            )

    def test_max_width_uses_right_minus_left_and_zero_feedback_initialization(self) -> None:
        self.assertEqual(longest_line_width_from_rectangles(()), 0)
        self.assertEqual(longest_line_width_from_rectangles((TextRect(4, 1), TextRect(3, 15), TextRect(-2, 7))), 12)
        with self.assertRaises(TypeError):
            longest_line_width_from_rectangles((TextRect(-32769, 0),))
        with self.assertRaises(OverflowError):
            longest_line_width_from_rectangles((TextRect(-32768, 32767),))

    def test_bold_plan_uses_nonzero_length_frame_and_preserves_ui_boundary(self) -> None:
        plan = plan_set_bold_text("text-ref", (1, 5, 9), (0, 3, -2), 10)
        self.assertTrue(plan.initialize_visible)
        self.assertEqual(plan.initialize_selection, (0, 0))
        self.assertFalse(plan.initialize_selection_boolean)
        self.assertEqual([(item.start, item.end) for item in plan.selection_effects], [(15, 18), (19, 17)])
        self.assertFalse(FONT_METRICS_BLOCKED.implementation_allowed)
        self.assertFalse(SET_BOLD_TEXT_BLOCKED.implementation_allowed)
        with self.assertRaises(OverflowError):
            plan_set_bold_text("text-ref", (2**31 - 1,), (1,), 0)
        in_range = plan_set_bold_text("text-ref", (2**31 - 1,), (1,), -1)
        self.assertEqual(
            (in_range.selection_effects[0].start, in_range.selection_effects[0].end),
            (2**31 - 2, 2**31 - 1),
        )
