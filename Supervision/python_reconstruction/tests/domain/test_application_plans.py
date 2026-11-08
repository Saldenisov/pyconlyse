import unittest

from supervision_reconstruction.domain.application_plans import (
    CENTROID_FLOAT_CONVERSION_BLOCKED,
    DETAILS_DIALOG_BLOCKED,
    INIT_OPEN_CLOSE_BLOCKED,
    centroid_lines_from_i32,
    plan_details_display_dialog,
    plan_init_open_close,
)
from supervision_reconstruction.domain.dialog_error import DialogType


class ApplicationPlansTests(unittest.TestCase):
    def test_centroid_formula_node_and_bundle_order_after_i32_boundary(self) -> None:
        result = centroid_lines_from_i32(100, 200)
        self.assertEqual(result.ligne_x, (90, 200, 110, 200))
        self.assertEqual(result.ligne_z, (100, 210, 100, 190))
        with self.assertRaises(OverflowError):
            centroid_lines_from_i32(2**31 - 1, 0)
        self.assertFalse(CENTROID_FLOAT_CONVERSION_BLOCKED.implementation_allowed)

    def test_init_open_close_plan_preserves_true_directory_false_sequence(self) -> None:
        plan = plan_init_open_close("tree", "C:/root", "*.vi")
        self.assertEqual(
            plan.operations[0],
            "Invoke Tree Delete Tree Items (ÉditerÉltsArbre.Suppr) with True",
        )
        self.assertIn("Directory to Tree", plan.operations[1])
        self.assertEqual(
            plan.operations[2],
            "Invoke Tree Open/Close All (Ouvrir/Fermer.Tout) with False",
        )
        self.assertFalse(plan.blocked.implementation_allowed)

    def test_dialog_type_one_is_proven_ok_visibility_branch(self) -> None:
        ok = plan_details_display_dialog(1, True)
        other = plan_details_display_dialog(0, False)
        self.assertTrue(ok.ok_visible)
        self.assertFalse(ok.continue_visible)
        self.assertTrue(other.continue_visible)
        self.assertTrue(other.stop_visible)
        self.assertIs(ok.dialog_type, DialogType.OK_MESSAGE)
        with self.assertRaises(ValueError):
            plan_details_display_dialog(6, False)
        with self.assertRaises(TypeError):
            plan_details_display_dialog(True, False)  # type: ignore[arg-type]
        self.assertFalse(DETAILS_DIALOG_BLOCKED.implementation_allowed)
