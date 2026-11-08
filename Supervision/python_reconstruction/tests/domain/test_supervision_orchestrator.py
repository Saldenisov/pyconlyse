import csv
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.supervision_orchestrator import (
    DIRECT_CALLEES,
    EVENT_CASES,
    LifecycleStage,
    ORCHESTRATION_BLOCKED,
    TIMED_LOOP_FRAMES,
    build_supervision_orchestration_plan,
    validate_supervision_orchestration_plan,
)


class SupervisionOrchestratorTests(unittest.TestCase):
    def test_static_plan_has_exact_top_level_inventory_counts(self) -> None:
        plan = build_supervision_orchestration_plan()
        validate_supervision_orchestration_plan(plan)
        self.assertEqual([item.stage for item in plan.lifecycle], list(LifecycleStage))
        self.assertEqual(len(plan.event_cases), 34)
        self.assertEqual(len(plan.timed_loop_frames), 9)
        self.assertFalse(plan.blocked.implementation_allowed)
        self.assertEqual(plan.blocked.conversion_state, "failed")

    def test_event_identity_and_major_boundaries_remain_explicit(self) -> None:
        self.assertEqual(EVENT_CASES[0].selector_label, "Timeout")
        self.assertIn("machine_frequency", EVENT_CASES[1].boundary)
        self.assertIn("slit_position", EVENT_CASES[2].boundary)
        self.assertEqual(EVENT_CASES[3].selector_label, "Translateurs: value change")
        self.assertIn("translator_stop", EVENT_CASES[3].boundary)
        self.assertIn("beamline_commands", EVENT_CASES[19].boundary)
        self.assertIn("beamline_commands", EVENT_CASES[20].boundary)
        for index in (7, 12, 13, 26):
            self.assertIn("diagnostic_events", EVENT_CASES[index].boundary)
        for index in (4, 5, 8, 9, 10, 11):
            self.assertIn("digital_command_events", EVENT_CASES[index].boundary)
        for index in (17, 18):
            self.assertIn("page_command_events", EVENT_CASES[index].boundary)
        self.assertIn("motor/camera", EVENT_CASES[27].boundary)
        self.assertIn("motor/camera", EVENT_CASES[30].boundary)
        labels = "\n".join(case.selector_label for case in EVENT_CASES)
        for state in ("TIR", "PRE-TIR", "VEILLE", "ARRET", "STOP"):
            self.assertNotIn(state, labels)

    def test_timed_and_stop_contracts_are_inventory_not_scheduler_or_safety_claims(self) -> None:
        plan = build_supervision_orchestration_plan()
        self.assertEqual([frame.index for frame in TIMED_LOOP_FRAMES], list(range(9)))
        self.assertIn("1 kHz timing base", plan.timing_labels)
        self.assertEqual(plan.stop_dependency.signal, "lowercase stop (distinct from stop motor)")
        self.assertEqual(plan.stop_dependency.release_order, ("addressed CmdLib8742.AbortMotion", "CmdLib8742.Shutdown"))
        self.assertIn("safe state", plan.stop_dependency.guarantee_not_proven)

    def test_direct_callee_evidence_remains_incomplete(self) -> None:
        self.assertFalse(DIRECT_CALLEES.completeness_proven)
        self.assertEqual(DIRECT_CALLEES.known_instance_counts, (("AbortMotion.vi", 3), ("Moteurs SdC GoTo.vi", 8), ("sous vi LigneCentroide2.vi", 1)))
        self.assertEqual(len(DIRECT_CALLEES.minimum_proven_direct_names), 4)

    def test_machine_readable_lvkit_and_ledger_match_topology_counts(self) -> None:
        supervision = Path(__file__).resolve().parents[3]
        description_path = supervision / "analysis" / "lvkit_eval" / "batch_0_8_4_minimal_vilib" / "descriptions" / "0_SUP_ELYSE.json"
        description = json.loads(description_path.read_text(encoding="utf-8"))

        scopes = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                if value.get("kind") == "scope":
                    scopes.append(value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(description["body"])
        by_uid = {int(scope["uid"]): scope for scope in scopes}
        self.assertEqual([frame["label"] for frame in by_uid[988]["frames"]], ["0", "1", "2", "3", "4"])
        self.assertEqual(len(by_uid[5909]["frames"]), len(EVENT_CASES))
        self.assertEqual(len(by_uid[16409]["frames"]), len(TIMED_LOOP_FRAMES))

        ledger_path = supervision / "analysis" / "expected_selector_frame_ledger.csv"
        with ledger_path.open(encoding="utf-8", newline="") as handle:
            outer_rows = [
                row for row in csv.DictReader(handle)
                if row["vi_name"] == "0_SUP_ELYSE.vi" and row["structure_uid"] == "988"
            ]
        self.assertEqual([row["frame_label"] for row in outer_rows], ["0", "1", "2", "3", "4"])

    def test_unresolved_boundaries_include_external_control_and_state_machine_limits(self) -> None:
        text = "\n".join(ORCHESTRATION_BLOCKED.unresolved_boundaries)
        self.assertIn("Tango", text)
        self.assertIn("CmdLib", text)
        self.assertIn("TIR/PRE-TIR/VEILLE/ARRET", text)


if __name__ == "__main__":
    unittest.main()
