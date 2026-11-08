import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from supervision_reconstruction.domain.translator_stop import (
    EVENT_FRAME_PATHS_PATH,
    LOOP_LEDGER_PATH,
    LVKIT_DESCRIPTION_PATH,
    LVKIT_DESCRIPTION_SHA256,
    NAMED_CAPTURE_PATH,
    NAMED_CAPTURE_SHA256,
    POLLING_SELECTOR_EXPRESSION,
    REVIEWED_EXTRACTED_COPY_SHA256,
    SOURCE_VI_SHA256,
    SOURCE_LIBRARY_PATH,
    SOURCE_LIBRARY_SHA256,
    STATIC_AUDIT_PATH,
    build_translator_stop_plan,
    evaluate_translator_loop_selector,
    validate_translator_stop_plan,
)


def _walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


class TranslatorStopTests(unittest.TestCase):
    def test_plan_retains_exact_evidenced_sequence_and_is_non_executable(self) -> None:
        plan = build_translator_stop_plan()
        validate_translator_stop_plan(plan)

        self.assertEqual((plan.event_structure_uid, plan.event_case_index), (5909, 3))
        self.assertEqual((plan.selector_uid, plan.selector_case_index), (56667, 0))
        self.assertEqual(plan.sequence_uid, 71948)
        self.assertEqual([frame.index for frame in plan.frames], [0, 1, 2, 3])
        self.assertFalse(plan.implementation_allowed)
        self.assertEqual(plan.visual_frame_mapping_status, "UNMAPPED")
        self.assertTrue(plan.manual_capture_shows_default)
        self.assertFalse(plan.lvkit_reports_default)
        self.assertFalse(plan.extracted_copy_matches_evidence_source)

    def test_exact_digital_bits_screen_positions_and_psp_boundary_are_preserved(self) -> None:
        plan = build_translator_stop_plan()
        start, positions, _, release = plan.frames
        start_write = start.shared_variable_write
        position_write = positions.shared_variable_write
        release_write = release.shared_variable_write

        self.assertIsNotNone(start_write)
        self.assertIsNotNone(position_write)
        self.assertIsNotNone(release_write)
        assert start_write is not None
        assert position_write is not None
        assert release_write is not None
        self.assertEqual(start_write.logical_variable, "WCM5G:")
        self.assertEqual(start_write.connection_refnum, 47)
        self.assertEqual(
            start_write.psp_url,
            "ni.var.psp://localhost/SUPERVISION/C5_OUT_DIO96",
        )
        self.assertEqual(
            [(item.field, item.value) for item in start_write.assignments],
            [
                ("01 CPB1 b79 Alimentation moteur", True),
                ("03 CPB3 b75 M/A Caméra chambre de préparation", False),
                ("05 CPB5 b71 M/A Caméra Miroir", False),
                ("07 CPB7 b67 M/A Eclairage Ecran 1", False),
                ("09 CPC1 b63 M/A Caméra Ecran 1", False),
                ("13 CPC5 b55 M/A Eclairage Ecran 2", False),
                ("15 CPC7 b51 M/A Caméra Ecran 2", False),
                ("19 DPA3 b92 M/A Eclairage Ecran 3", False),
                ("21 DPA5 b88 M/A Caméra Ecran 3", False),
                ("31 DPB7 b68 M/A Alimentation Ecrans", True),
                ("26 DPB2 b78 Cmd Miroir LASER HORS", True),
            ],
        )
        self.assertEqual(
            [(item.field, item.value) for item in position_write.assignments],
            [
                ("04 OUT04 b17 Cmd position translateur Ecran 1", 2.126),
                ("05 OUT05 b21 Cmd position translateur Ecran 2", 2.126),
                ("06 OUT06 b25 Cmd position translateur Ecran 3", 2.126),
            ],
        )
        self.assertEqual(position_write.logical_variable, "WCM5D:")
        self.assertEqual(position_write.connection_refnum, 43)
        self.assertIsNone(position_write.psp_url)
        self.assertTrue(all(item.value is False for item in release_write.assignments))
        for write in (start_write, position_write, release_write):
            self.assertTrue(write.external_effects_blocked)
            self.assertTrue(write.manual_approval_required)

    def test_neutral_polling_selector_expression_boundaries(self) -> None:
        self.assertEqual(POLLING_SELECTOR_EXPRESSION.wait_ms, 100)
        self.assertEqual(POLLING_SELECTOR_EXPRESSION.iteration_comparison_threshold, 1200)
        self.assertEqual(POLLING_SELECTOR_EXPRESSION.measurement_comparison_threshold, 22.7)
        self.assertEqual(POLLING_SELECTOR_EXPRESSION.termination_semantics, "NATIVE_UNVERIFIED")
        self.assertFalse(
            evaluate_translator_loop_selector(
                iteration=1200,
                position_miroir_laser=22.7,
                etat_t1=22.7,
                etat_mlaser_en=22.7,
            )
        )
        self.assertTrue(
            evaluate_translator_loop_selector(
                iteration=1201,
                position_miroir_laser=22.7,
                etat_t1=22.7,
                etat_mlaser_en=22.7,
            )
        )
        self.assertTrue(
            evaluate_translator_loop_selector(
                iteration=0,
                position_miroir_laser=22.699,
                etat_t1=0,
                etat_mlaser_en=-1,
            )
        )
        self.assertFalse(
            evaluate_translator_loop_selector(
                iteration=0,
                position_miroir_laser=22.699,
                etat_t1=22.7,
                etat_mlaser_en=0,
            )
        )
        with self.assertRaises(TypeError):
            evaluate_translator_loop_selector(
                iteration=True,
                position_miroir_laser=0,
                etat_t1=0,
                etat_mlaser_en=0,
            )
        with self.assertRaises(ValueError):
            evaluate_translator_loop_selector(
                iteration=0,
                position_miroir_laser=float("nan"),
                etat_t1=0,
                etat_mlaser_en=0,
            )

    def test_validator_rejects_mutated_write_boundaries_and_tab_metadata(self) -> None:
        plan = build_translator_stop_plan()
        start, positions, poll, release = plan.frames
        assert start.shared_variable_write is not None
        assert start.tab_color_write is not None

        mutations = (
            replace(plan, event_label="WRONG"),
            replace(plan, selector_case_label="WRONG"),
            replace(plan, unresolved_semantics=()),
            replace(
                plan,
                frames=(
                    replace(
                        start,
                        shared_variable_write=replace(
                            start.shared_variable_write,
                            connection_refnum=99,
                        ),
                    ),
                    positions,
                    poll,
                    release,
                ),
            ),
            replace(
                plan,
                frames=(
                    replace(
                        start,
                        shared_variable_write=replace(
                            start.shared_variable_write,
                            psp_url="ni.var.psp://localhost/WRONG",
                        ),
                    ),
                    positions,
                    poll,
                    release,
                ),
            ),
            replace(
                plan,
                frames=(
                    replace(
                        start,
                        shared_variable_write=replace(
                            start.shared_variable_write,
                            simple_error_handler_follows_write=False,
                        ),
                    ),
                    positions,
                    poll,
                    release,
                ),
            ),
            replace(
                plan,
                frames=(
                    replace(
                        start,
                        tab_color_write=replace(start.tab_color_write, raw_value=0),
                    ),
                    positions,
                    poll,
                    release,
                ),
            ),
        )
        for mutation in mutations:
            with self.assertRaises(ValueError):
                validate_translator_stop_plan(mutation)

    def test_lvkit_static_audit_loop_ledger_and_named_capture_cross_check(self) -> None:
        repository = Path(__file__).resolve().parents[4]
        description_path = repository / LVKIT_DESCRIPTION_PATH
        self.assertEqual(
            hashlib.sha256(description_path.read_bytes()).hexdigest().upper(),
            LVKIT_DESCRIPTION_SHA256,
        )
        description = json.loads(description_path.read_text(encoding="utf-8"))
        scopes = {
            int(item["uid"]): item
            for item in _walk(description["body"])
            if item.get("kind") == "scope" and item.get("uid") in {"56667", "71948", "80242"}
        }
        self.assertEqual(scopes[56667]["frames"][0]["label"], "      Arrêt ")
        self.assertEqual([frame["label"] for frame in scopes[71948]["frames"]], ["0", "1", "2", "3"])

        frame_zero = scopes[71948]["frames"][0]["body"]
        frame_one = scopes[71948]["frames"][1]["body"]
        frame_three = scopes[71948]["frames"][3]["body"]
        bundle_zero = next(node for node in frame_zero if node.get("uid") == "53524")
        bundle_one = next(node for node in frame_one if node.get("uid") == "64980")
        bundle_three = next(node for node in frame_three if node.get("uid") == "58268")
        self.assertEqual(bundle_zero["inputs"][0]["net"]["bare"], "WCM5G:")
        self.assertEqual(bundle_one["inputs"][0]["net"]["bare"], "WCM5D:")
        self.assertEqual(bundle_three["inputs"][0]["net"]["bare"], "WCM5G:")
        self.assertEqual(
            [entry["net"]["bare"] for entry in bundle_one["inputs"][1:]],
            ["2.126", "2.126", "2.126"],
        )
        loop_nodes = scopes[80242]["frames"][0]["body"]
        by_uid = {int(node["uid"]): node for node in loop_nodes if node.get("kind") == "instance"}
        self.assertEqual(by_uid[54545]["inputs"][0]["net"]["bare"], "100")
        self.assertEqual(by_uid[55105]["inputs"][0]["net"]["bare"], "1200")
        for uid in (62768, 64817, 81254):
            self.assertEqual(by_uid[uid]["inputs"][0]["net"]["bare"], "22.7")

        with (repository / STATIC_AUDIT_PATH).open(encoding="utf-8", newline="") as handle:
            audit_rows = list(csv.DictReader(handle))
        loop_row = next(
            row for row in audit_rows
            if row["vi_name"] == "0_SUP_ELYSE.vi" and row["structure_uid"] == "80242"
        )
        self.assertEqual(loop_row["audit_status"], "STATIC_EXTRACTED_VISUAL_UNCONFIRMED")
        self.assertEqual(loop_row["direct_wait_ms_as_parsed"], '["100"]')

        with (repository / LOOP_LEDGER_PATH).open(encoding="utf-8", newline="") as handle:
            ledger_rows = list(csv.DictReader(handle))
        ledger_row = next(row for row in ledger_rows if row["structure_uid"] == "80242")
        self.assertEqual(ledger_row["mapping_status"], "UNMAPPED")

        event_paths = (repository / EVENT_FRAME_PATHS_PATH).read_text(encoding="utf-8")
        self.assertIn('3,5909,event,3,"[3] ""Translateurs"": Value Change"', event_paths)
        self.assertIn('3,71948,sequence,2,2', event_paths)

        named_capture = repository / NAMED_CAPTURE_PATH
        self.assertTrue(named_capture.is_file())
        self.assertEqual(hashlib.sha256(named_capture.read_bytes()).hexdigest().upper(), NAMED_CAPTURE_SHA256)
        self.assertEqual(SOURCE_VI_SHA256, "B7B79636E77D7756A5896EDD132F7E3B24301394A04893D9A73938073C210A7B")
        source_library = repository / SOURCE_LIBRARY_PATH
        self.assertEqual(hashlib.sha256(source_library.read_bytes()).hexdigest().upper(), SOURCE_LIBRARY_SHA256)
        source_vi = repository / "Supervision" / "extracted" / "PILOTAGE_ELYSE_SUP" / "SUPERVISION_VIs" / "0_SUP_ELYSE.vi"
        self.assertEqual(hashlib.sha256(source_vi.read_bytes()).hexdigest().upper(), REVIEWED_EXTRACTED_COPY_SHA256)
        self.assertNotEqual(REVIEWED_EXTRACTED_COPY_SHA256, SOURCE_VI_SHA256)


if __name__ == "__main__":
    unittest.main()
