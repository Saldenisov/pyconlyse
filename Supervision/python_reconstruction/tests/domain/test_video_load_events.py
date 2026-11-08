from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from supervision_reconstruction.domain.event_effects import (
    EVIDENCE_PATH,
    EVIDENCE_SHA256,
    SOURCE_VI_SHA256,
    EffectIntent,
)
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster
from supervision_reconstruction.domain.load_events import (
    TREE_ERROR,
    LegacyPathState,
    plan_load_toggle,
    plan_validate_load,
    project_tree_selection,
)
from supervision_reconstruction.domain.video_events import (
    CHANNEL_ERROR,
    THRESHOLD_ERROR,
    VIDEO_TOOL_ERROR,
    plan_camera_channel_change,
    plan_density_change,
    plan_save_image,
    plan_threshold_mouse_up,
    plan_video_tools,
)

OK = ErrorCluster(False, 0, "warning")
ERROR = ErrorCluster(True, 44, "driver source")
SUPERVISION = Path(__file__).resolve().parents[3]


class VideoToolTests(unittest.TestCase):
    def test_all_64_masks_and_default(self):
        for mask in range(64):
            with self.subTest(mask=mask):
                p = plan_video_tools(
                    tuple(bool(mask & (1 << i)) for i in range(6)),
                    final_property_error=OK,
                )
                self.assertEqual(p.mask, mask)
                self.assertEqual(p.reset_tools, (False,) * 6)
                self.assertEqual([x.value for x in p.center_properties], [250, 250])
                self.assertIsNone(p.delay_ms)
                self.assertIsNone(p.ter_text)
                self.assertTrue(p.external_effects_blocked)
                expected = mask if mask in (1, 2, 4, 8, 16, 32) else 0
                self.assertEqual(p.selected_case, expected)
                if not expected:
                    self.assertEqual(p.branch_properties, ())

    def test_zoom_labels_do_not_override_values(self):
        for mask, expected in ((1, 0.5), (2, 1.0), (4, 2.0), (8, 4.0)):
            p = plan_video_tools(
                tuple(bool(mask & (1 << i)) for i in range(6)), final_property_error=OK
            )
            self.assertEqual(len(p.branch_properties), 4)
            self.assertEqual([x.value for x in p.branch_properties], [expected] * 4)

    def test_roi_250_and_clear_are_rectangles_not_delays(self):
        for mask, expected in ((16, (200, 200, 300, 300)), (32, (0, 0, 0, 0))):
            p = plan_video_tools(
                tuple(bool(mask & (1 << i)) for i in range(6)), final_property_error=OK
            )
            roi = p.branch_properties[0].value
            self.assertEqual(roi.global_rectangle, expected)
            self.assertEqual(roi.points, expected)
            self.assertEqual((roi.contour_type, roi.roi_type), (0, 3))

    def test_final_error_not_assumed_merge_result(self):
        p = plan_video_tools((False,) * 6, final_property_error=ERROR)
        self.assertEqual(p.ter_text, VIDEO_TOOL_ERROR + ERROR.source)

    def test_invalid_cluster(self):
        for values in ((False,) * 5, (False,) * 7, (0,) * 6, (None,) * 6):
            with self.assertRaises(ValueError):
                plan_video_tools(values, final_property_error=OK)


class CameraTests(unittest.TestCase):
    def test_threshold_sequence_and_always_wait_false(self):
        for error in (OK, ERROR):
            p = plan_threshold_mouse_up(final_error=error)
            self.assertEqual(p.event_index, 24)
            self.assertEqual([f.index for f in p.frames], [0, 1, 2, 3])
            self.assertEqual(p.final_patches[0].value, False)
            self.assertEqual(p.final_patches[0].control, "Wait")
            self.assertEqual(p.frames[0].effects[0].arguments, (("ms", 300),))
            self.assertEqual(p.frames[3].effects[0].arguments, (("ms", 50),))
            self.assertEqual(
                p.ter_text, THRESHOLD_ERROR + error.source if error.status else None
            )

    def test_channel_clear_errors_and_delay_frames(self):
        p = plan_camera_channel_change(final_error=OK)
        self.assertEqual([f.index for f in p.frames], list(range(5)))
        self.assertEqual(p.frames[0].effects[0].arguments, (("ms", 500),))
        self.assertEqual(p.frames[2].effects[0].operation, "Clear Errors.vi")
        self.assertEqual(p.frames[2].effects[1].arguments, (("ms", 500),))
        self.assertIn("NOT Event NewVal", p.frames[3].effects[1].arguments[0][1])

    def test_channel_error_does_not_reset_wait(self):
        p = plan_camera_channel_change(final_error=ERROR)
        self.assertEqual(p.pre_sequence_patches[0].value, True)
        self.assertFalse(any(x.control == "Wait" for x in p.final_patches))
        self.assertEqual(p.ter_text, CHANNEL_ERROR + ERROR.source)

    def test_formatter_output_is_not_synthesized(self):
        p = plan_camera_channel_change(final_error=OK)
        self.assertFalse(any(x.control == "TME" for x in p.final_patches))
        p = plan_camera_channel_change(final_error=OK, formatted_text="external text")
        self.assertEqual(p.final_patches[0].value, "external text")
        p = plan_camera_channel_change(final_error=ERROR, formatted_text="unused")
        self.assertFalse(any(x.control == "TME" for x in p.final_patches))

    def test_density_true_branch_stays_dead(self):
        p = plan_density_change()
        self.assertIs(p.selector, False)
        self.assertEqual(p.reachable_effects, ())
        self.assertIn(17485, p.dead_branch_uids)


class SaveImageTests(unittest.TestCase):
    def test_false_no_dialog_or_file_access(self):
        p = plan_save_image(False)
        self.assertEqual(p.prepare_effects, ())
        self.assertEqual(p.write_effects, ())
        self.assertFalse(p.reset_value)

    def test_pending_dialog_and_year_directory(self):
        p = plan_save_image(True, resolved_year=2026)
        self.assertTrue(p.dialog_pending)
        self.assertEqual(p.start_path, "Z:\\Manips\\Mesures\\2026")
        self.assertEqual(p.write_effects, ())
        self.assertEqual(p.unresolved_image_uid, 83225)

    def test_cancelled_no_palette_or_write(self):
        p = plan_save_image(True, resolved_year=2026, dialog_cancelled=True)
        self.assertEqual(p.write_effects, ())
        self.assertEqual(len(p.prepare_effects), 3)

    def test_not_cancelled_tiff_defaults_and_no_write_execution(self):
        p = plan_save_image(
            True,
            resolved_year=2026,
            dialog_cancelled=False,
            selected_path="does-not-exist.tif",
        )
        self.assertEqual([x.node_uid for x in p.write_effects], [56663, 83086])
        args = dict(p.write_effects[1].arguments)
        self.assertEqual(
            [args[x] for x in ("Rows Per Strip", "Photometric", "Compression Type")],
            [0, 1, 0],
        )
        self.assertTrue(all(x.external_effects_blocked for x in p.write_effects))

    def test_invalid_event_or_external_results(self):
        for kwargs in (
            {"resolved_year": True},
            {"resolved_year": 2**31},
            {"resolved_year": 2026, "dialog_cancelled": 0},
            {"resolved_year": 2026, "dialog_cancelled": False},
        ):
            with self.assertRaises(ValueError):
                plan_save_image(True, **kwargs)
        with self.assertRaises(ValueError):
            plan_save_image(1)


class FileBrowserTests(unittest.TestCase):
    def test_load_false_closes_reference_and_changes_tabs(self):
        p = plan_load_toggle(False)
        self.assertEqual([x.node_uid for x in p.effects], [20457, 20468])
        self.assertEqual([x.value for x in p.ui_patches], [2, 0])
        self.assertEqual(p.hardware_commands, ())

    def test_valid_directory_uses_cache_without_dialog(self):
        p = plan_load_toggle(True, cached_directory="not-existing-directory")
        self.assertFalse(p.dialog_required)
        self.assertEqual([x.node_uid for x in p.effects], [20926, 4581])

    def test_empty_and_not_a_path_have_distinct_inputs_same_branch(self):
        for state in (LegacyPathState.EMPTY, LegacyPathState.NOT_A_PATH):
            p = plan_load_toggle(True, path_state=state, dialog_directory="selected")
            self.assertTrue(p.dialog_required)
            self.assertEqual(p.selected_directory, "selected")
            self.assertEqual([x.node_uid for x in p.effects], [20536, 20926, 4581])
            self.assertEqual(p.ui_patches[0].control, "Chemin des fichiers")

    def test_pending_dialog_does_not_invent_result(self):
        p = plan_load_toggle(True, path_state=LegacyPathState.EMPTY)
        self.assertEqual(p.selected_directory, None)
        self.assertEqual([x.node_uid for x in p.effects], [20536])

    def test_validate_false_only_button_reset(self):
        p = plan_validate_load(False)
        self.assertEqual(p.frames, ())
        self.assertFalse(p.reset_value)

    def test_validate_true_discards_ten_read_results_no_parameter_apply(self):
        p = plan_validate_load(True, current_tag="nonexistent-file")
        self.assertEqual(
            [dict(x.arguments)["count"] for x in p.frames[0].effects], list(range(10))
        )
        self.assertFalse(p.read_outputs_consumed)
        self.assertEqual(p.equipment_updates, ())
        self.assertEqual([x.value for x in p.frames[1].ui_patches][-2:], [2, 0])

    def test_tree_tag_write_not_error_gated(self):
        for error in (OK, ERROR):
            p = project_tree_selection(
                variant_string_result="externally converted", final_error=error
            )
            self.assertEqual(p.current_tag, "externally converted")
            self.assertTrue(p.tag_written_even_on_error)
            self.assertEqual(
                p.ter_text, TREE_ERROR + error.source if error.status else None
            )


class RemainingEvidenceTests(unittest.TestCase):
    def test_frozen_evidence_and_all_source_artifacts(self):
        path = SUPERVISION / EVIDENCE_PATH
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(), EVIDENCE_SHA256
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["source_vi_sha256"], SOURCE_VI_SHA256)
        for row in data["artifacts"]:
            with self.subTest(path=row["path"]):
                self.assertEqual(
                    hashlib.sha256((SUPERVISION / row["path"]).read_bytes())
                    .hexdigest()
                    .upper(),
                    row["sha256"],
                )

    def test_dead_density_and_cancel_selector_original_evidence(self):
        data = json.loads((SUPERVISION / EVIDENCE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(data["scopes"]["24546"]["selector"]["bare"], "False")
        case = data["scopes"]["173100"]
        self.assertEqual(case["selector"]["terminal"], "10")
        uids = {x["uid"] for x in case["frames"][0]["nodes"]}
        self.assertTrue({"56663", "83086"}.issubset(uids))
        self.assertEqual(case["frames"][1]["nodes"], [])

    def test_effects_are_data_not_callables(self):
        effect = EffectIntent("not an adapter", 1)
        self.assertFalse(callable(effect))
        self.assertTrue(effect.external_effects_blocked)


if __name__ == "__main__":
    unittest.main()
