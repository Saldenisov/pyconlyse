import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from supervision_reconstruction.domain import lifecycle_tail as model

SUPERVISION = Path(__file__).resolve().parents[3]


class LifecycleTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = SUPERVISION / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_source_and_artifact_hashes_match(self):
        self.assertEqual(
            hashlib.sha256(self.path.read_bytes()).hexdigest().upper(),
            model.EVIDENCE_SHA256,
        )
        for row in self.proof["artifacts"]:
            self.assertEqual(
                hashlib.sha256((SUPERVISION / row["path"]).read_bytes())
                .hexdigest()
                .upper(),
                row["sha256"],
            )
        self.assertFalse(self.proof["vi_or_generated_execution"])

    def test_three_resource_groups_are_not_a_global_shutdown_order(self):
        plan = model.build_lifecycle_tail_plan()
        self.assertEqual(
            [
                (group.resource_family, group.visible_resource_count)
                for group in plan.cleanup_groups
            ],
            [("PSP", 13), ("IMAQ", 9), ("CmdLib", 1)],
        )
        self.assertFalse(plan.resource_groups_have_total_order)
        self.assertFalse(plan.all_stop_paths_reach_cleanup_proven)
        self.assertFalse(plan.hardware_safe_state_established)
        self.assertFalse(plan.stop_local_reset_value)
        self.assertTrue(
            all(group.external_effects_blocked for group in plan.cleanup_groups)
        )

    def test_psp_error_is_retained_unlike_explicit_image_initial_error(self):
        groups = model.CLEANUP_GROUPS
        self.assertIn("uninitialized", groups[0].initial_error_boundary)
        self.assertIn("explicit no-error", groups[1].initial_error_boundary)
        self.assertTrue(self.proof["cleanup"]["psp_shift_register_is_uninitialized"])
        self.assertTrue(
            self.proof["cleanup"]["image_error_shift_register_is_initialized"]
        )
        saved = {node["uid"]: node for node in self.proof["cleanup"]["saved_nodes"]}
        psp = saved["11851"]
        image = saved["21424"]
        self.assertFalse(
            next(t for t in psp["tunnels"] if t["tunnel_type"] == "lSR")[
                "sr_initialized"
            ]
        )
        self.assertTrue(
            next(t for t in image["tunnels"] if t["tunnel_type"] == "lSR")[
                "sr_initialized"
            ]
        )

    def test_one_motor_address_does_not_prove_all_axes_stop(self):
        motor = model.CLEANUP_GROUPS[2]
        self.assertEqual(
            motor.wire_order[:2], ("AbortMotion.vi for supplied address", "Shutdown.vi")
        )
        self.assertFalse(motor.hardware_safe_state_established)
        self.assertEqual(
            self.proof["cleanup"]["motor_error_wire_order"], [177515, 192398, 194898]
        )
        self.assertTrue(
            self.proof["cleanup"]["only_one_supplied_motor_address_visible"]
        )

    def test_all_15_formula_expressions_match_original_source_text(self):
        actual = {item.node_uid: item.expression for item in model.RETIRED_FORMULAS}
        expected = {
            int(item["uid"]): item["expression"]
            for item in self.proof["retired_formula_frame"]["formulas"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 15)

    def test_retired_outputs_have_no_consumers_and_are_not_live_calibrations(self):
        frame = self.proof["retired_formula_frame"]
        self.assertEqual(frame["native_label"], "POUBELLE")
        wired = set(frame["original"]["wires"][0])
        self.assertEqual(len(frame["original"]["wires"]), 1)
        for formula in frame["formulas"]:
            self.assertTrue(set(formula["zero_wired_input_terminals"]).issubset(wired))
            self.assertFalse(set(formula["unwired_output_terminals"]) & wired)
        self.assertTrue(
            all(
                not item.live_calibration and not item.output_has_consumers
                for item in model.RETIRED_FORMULAS
            )
        )
        self.assertTrue(frame["not_evaluated_in_python"])

    def test_inventory_is_immutable_and_has_no_executor(self):
        plan = model.build_lifecycle_tail_plan()
        with self.assertRaises(FrozenInstanceError):
            plan.hardware_safe_state_established = True
        self.assertFalse(hasattr(plan, "execute"))


if __name__ == "__main__":
    unittest.main()
