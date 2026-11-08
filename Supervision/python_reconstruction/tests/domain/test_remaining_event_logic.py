from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import unittest
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from supervision_reconstruction.domain.autotune_events import (
    NETLIST_PATH,
    NETLIST_SHA256,
    AutotuneStage,
    autotune_outer_termination,
    plan_autotune,
    plan_autotune_camera_switch,
    project_autotune_iteration,
)
from supervision_reconstruction.domain.event_effects import (
    EVIDENCE_PATH,
    SOURCE_VI_SHA256,
)
from supervision_reconstruction.domain.fw102x_errors import ErrorCluster
from supervision_reconstruction.domain.load_events import plan_load_toggle
from supervision_reconstruction.domain.motion_events import (
    plan_manual_jog,
    plan_motor_initialization,
    project_jog_poll,
    project_motion_error,
)
from supervision_reconstruction.domain.supervision_orchestrator import (
    EVENT_CASES,
    EVENT_MODEL_MODULES,
)
from supervision_reconstruction.domain.timeout_events import (
    REFRESH_RULES,
    plan_timeout_counter_request,
    plan_timeout_visual_refresh,
    project_timeout_fields,
    timeout_motor_numbers,
    timeout_read_chain,
)
from supervision_reconstruction.domain.translator_selection import (
    TranslatorSelection,
    plan_translator_selection,
)

SUPERVISION = Path(__file__).resolve().parents[3]
OK = ErrorCluster(False, 0, "")
ERROR = ErrorCluster(True, -1, "external driver error")


def walk(body):
    for node in body:
        yield node
        for frame in node.get("frames", []):
            yield from walk(frame["body"])


class MotionEventTests(unittest.TestCase):
    def test_pending_discovery_is_not_success(self):
        p = plan_motor_initialization()
        self.assertFalse(p.discovery_key_supplied)
        self.assertEqual(p.zero_motor_numbers, ())
        self.assertEqual(len(p.frames[1].effects), 1)
        self.assertTrue(p.external_effects_blocked)

    def test_empty_discovery_shows_dialog_without_zeroing(self):
        p = plan_motor_initialization("")
        self.assertEqual(p.zero_motor_numbers, ())
        self.assertEqual(p.no_devices_message, "No devices found during discovery.")
        self.assertEqual(p.frames[1].effects[-1].operation, "One Button Dialog")

    def test_identification_zeroes_all_four_axes_as_intents(self):
        p = plan_motor_initialization("external device key")
        self.assertEqual(p.zero_motor_numbers, (1, 2, 3, 4))
        self.assertEqual(
            dict(p.frames[1].effects[0].arguments), {"timeout": 5000, "flag": True}
        )
        self.assertEqual(dict(p.frames[1].effects[1].arguments)["device_address"], 0)
        self.assertEqual([x.value for x in p.frames[0].ui_patches], [False] * 5)
        self.assertEqual(
            [x.value for x in p.frames[2].ui_patches], [True] * 5 + [False]
        )

    def test_four_jog_labels_axis_and_sign(self):
        for label, event, motor, steps in (
            ("Move forward X", 28, 3, 10),
            ("Move forward Y", 28, 4, 10),
            ("Move reverse X", 29, 3, -10),
            ("Move reverse Y", 29, 4, -10),
        ):
            with self.subTest(label=label):
                p = plan_manual_jog(label, motor_numbers=(3, 4), relative_steps=10)
                self.assertEqual(
                    (p.event_index, p.motor_number, p.signed_steps),
                    (event, motor, steps),
                )
                self.assertFalse(p.event_newval_guarded)
                self.assertIsNone(p.loop_timeout_ms)
                self.assertEqual(len(p.hide_patches), 6)
                self.assertEqual(len(p.restore_patches), 7)
                self.assertEqual(p.hide_patches[-1].value, 2)
                self.assertEqual(p.restore_patches[-1].value, 0)
                self.assertTrue(
                    all(x.external_effects_blocked for x in p.polling_calls)
                )

    def test_jog_poll_truth_table_and_unconditional_position(self):
        for event, done, status, stop in itertools.product(
            (28, 29), (False, True), (False, True), (False, True)
        ):
            p = project_jog_poll(
                event_index=event,
                motion_done=done,
                motion_done_error=ErrorCluster(status, 0, ""),
                stop_motor=stop,
                position_result=-123,
            )
            self.assertEqual(p.terminate, done or status or stop)
            self.assertEqual(p.motor_position, -123)
            self.assertEqual(p.abort_intent is not None, stop)
            if stop:
                self.assertEqual(
                    p.abort_intent.node_uid, 95968 if event == 28 else 266362
                )

    def test_motion_errors_use_event_specific_journal_nodes(self):
        for index, uid in ((27, 77718), (28, 170563), (29, 266960)):
            self.assertIsNone(project_motion_error(OK, event_index=index))
            p = project_motion_error(ERROR, event_index=index)
            self.assertEqual(p.node_uid, uid)
            self.assertEqual(dict(p.arguments)["path"], "c:\\Erreurs.xls")
            self.assertEqual(
                dict(p.arguments)["text"], "Erreur N° -1 : external driver error"
            )

    def test_jog_unknown_axis_and_coercion_are_not_invented(self):
        for label, motors, steps in (
            ("typo", (1, 2), 5),
            ("Move forward Y", (), 5),
            ("Move forward X", (True,), 5),
            ("Move forward X", (1,), True),
            ("Move reverse X", (1,), -(2**31)),
        ):
            with self.assertRaises(ValueError):
                plan_manual_jog(label, motor_numbers=motors, relative_steps=steps)


class AutotuneTests(unittest.TestCase):
    def test_all_stages_boundary_and_direction_matrix(self):
        expected = (
            (AutotuneStage.CHANNEL3_X, 10, 2, 10),
            (AutotuneStage.CHANNEL3_Y, 10, 9, 1),
            (AutotuneStage.CHANNEL2_X, 3, 10, 2),
            (AutotuneStage.CHANNEL2_Y, 3, 9, 1),
        )
        for stage, steps, high, low in expected:
            for coordinate in (248.999, 249.0, 250.0, 251.0, 251.001):
                for stop, error in itertools.product((False, True), repeat=2):
                    with self.subTest(
                        stage=stage, coordinate=coordinate, stop=stop, error=error
                    ):
                        p = project_autotune_iteration(
                            stage, coordinate, stop_motor=stop, motor_error=error
                        )
                        in_band = 249 <= coordinate <= 251
                        self.assertEqual(p.in_band, in_band)
                        self.assertEqual(
                            p.terminate_inner_loop, in_band or stop or error
                        )
                        self.assertEqual(p.move_intent is None, in_band)
                        self.assertEqual(p.wait_ms, 3000)
                        self.assertFalse(p.freshness_after_wait_proven)
                        self.assertIsNone(p.maximum_iterations)
                        if not in_band:
                            args = dict(p.move_intent.arguments)
                            self.assertEqual(args["Relative Steps"], steps)
                            self.assertEqual(
                                args["true_connector_index"],
                                high if coordinate > 251 else low,
                            )
                            self.assertEqual(args["stop motor"], stop)
                            self.assertEqual(
                                args["other_boolean_defaults"], "unqualified"
                            )

    def test_outer_termination_uses_only_y_flags_and_stop(self):
        for a, b, stop in itertools.product((False, True), repeat=3):
            self.assertEqual(
                autotune_outer_termination(
                    channel3_y_in_band=a, channel2_y_in_band=b, stop_motor=stop
                ),
                (a and b) or stop,
            )

    def test_disabled_hide_is_not_enabled_and_completion_is_not_success(self):
        p = plan_autotune()
        self.assertFalse(p.complete_runtime)
        self.assertEqual(len(p.stage_order), 6)
        self.assertEqual(p.camera_switch_sequences, ((11854, 3), (35260, 2)))
        self.assertFalse(
            any(x.node_uid == p.disabled_control_hide_uid for x in p.entry_patches)
        )
        self.assertEqual(dict(p.completion_journal.arguments)["success_guard"], False)
        self.assertEqual(
            dict(p.completion_journal.arguments)["text"], "Autotune terminé "
        )
        self.assertTrue(p.completion_journal.external_effects_blocked)

    def test_nan_infinity_and_boolean_are_unqualified(self):
        for value in (float("nan"), float("inf"), float("-inf"), True, None):
            with self.assertRaises(ValueError):
                project_autotune_iteration(
                    AutotuneStage.CHANNEL3_X, value, stop_motor=False, motor_error=False
                )

    def test_camera_switch_has_eight_frames_and_error_does_not_reset_busy(self):
        for channel, error in itertools.product((2, 3), (OK, ERROR)):
            p = plan_autotune_camera_switch(channel, final_error=error)
            self.assertEqual([f.index for f in p.frames], list(range(8)))
            self.assertEqual(p.frames[0].ui_patches[1].value, channel)
            waits = [
                dict(e.arguments)["ms"]
                for f in p.frames
                for e in f.effects
                if e.operation == "Wait (ms)"
            ]
            self.assertEqual(waits, [500, 500, 3000])
            self.assertEqual(
                p.frames[6].ui_patches[0].control, "TER" if error.status else "Wait"
            )
            self.assertFalse(p.camera_error_skips_following_motion_stages)


class TimeoutTests(unittest.TestCase):
    def test_read_chain_error_order_and_independent_counter_read(self):
        chain = timeout_read_chain()
        self.assertEqual(len(chain), 14)
        self.assertEqual([x.frame_index for x in chain], [0] * 12 + [1, 2])
        for previous, current in zip(chain[:12], chain[1:13]):
            self.assertEqual(current.previous_error_node_uid, previous.node_uid)
        self.assertIsNone(chain[-1].previous_error_node_uid)
        self.assertTrue(chain[12].observed_url.endswith("/VTS"))
        self.assertFalse(any(x.local_result_write_error_gated for x in chain))

    def test_motor_selector_retains_empty_channel3_and_default(self):
        for channel, expected in (
            (0, ()),
            (3, ()),
            (1, (3, 4)),
            (2, (1, 2)),
            (4, (1, 2)),
            (65535, (1, 2)),
        ):
            self.assertEqual(timeout_motor_numbers(channel), expected)
        for channel in (True, -1, 65536, 1.0):
            with self.assertRaises(ValueError):
                timeout_motor_numbers(channel)

    def test_visual_refresh_only_copies_properties_and_formats_external_clock(self):
        frame = plan_timeout_visual_refresh(3)
        self.assertEqual(frame.index, 3)
        self.assertEqual(
            [x.node_uid for x in frame.effects], [13299, 3135, 22261, 22342]
        )
        self.assertEqual(frame.ui_patches[0].value, ())
        self.assertEqual(
            dict(frame.effects[-1].arguments)["format"], "Le %d/%m/%y   %H:%M:%S"
        )

    def test_counter_guard_and_all_sixteen_valid_field_selections(self):
        tasks = tuple(f"external task {i}" for i in range(8))
        page = tuple(float(i) for i in range(33))
        for n in (0.0, -1.0, 16.0):
            p = plan_timeout_counter_request(
                n, counter_task_identities=(), local_page_sync=()
            )
            self.assertFalse(p.legacy_guard)
            self.assertEqual(p.frames, ())
        for n in range(17, 33):
            p = plan_timeout_counter_request(
                n, counter_task_identities=tasks, local_page_sync=page
            )
            index = (n - 17) // 2
            self.assertEqual(p.task_index, index)
            self.assertEqual(p.page_field_indices, (16 + 2 * index, 17 + 2 * index))
            self.assertEqual([f.index for f in p.frames], [0, 1, 2])
            args = dict(p.frames[0].effects[0].arguments)
            self.assertEqual(args["task"], tasks[index])
            self.assertEqual(
                (args["delay"], args["width"]), (16.0 + 2 * index, 17.0 + 2 * index)
            )
            self.assertFalse(p.helper_error_controls_reset)
            self.assertEqual(p.frames[1].ui_patches[0].value, -1.0)

    def test_fractional_selection_retains_floor_but_invalid_index_fails_closed(self):
        p = plan_timeout_counter_request(
            18.999, counter_task_identities=("task",), local_page_sync=(0.0,) * 33
        )
        self.assertEqual(p.task_index, 0)
        for n in (16.1, 33.0, True, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                plan_timeout_counter_request(
                    n,
                    counter_task_identities=("task",) * 8,
                    local_page_sync=(0.0,) * 33,
                )

    def test_sixtysix_sparse_refreshes_and_h5_v5_original_anomaly(self):
        snapshots = defaultdict(dict)
        for i, rule in enumerate(REFRESH_RULES):
            snapshots[rule.source_cluster][rule.source_field] = (
                bool(i % 2) if rule.source_cluster == "DPS" else float(i)
            )
        patches = project_timeout_fields(snapshots)
        self.assertEqual(len(patches), 66)
        self.assertEqual(len({(p.control, p.property) for p in patches}), 66)
        values = {(p.control, p.property): p.value for p in patches}
        self.assertEqual(
            values["Voie déviée", "Correcteur H5.Lecture"],
            values["Voie déviée", "Correcteur V5.Lecture"],
        )
        self.assertFalse(any(p.control == "hardware" for p in patches))

    def test_missing_or_nonfinite_readback_is_not_fabricated(self):
        with self.assertRaisesRegex(ValueError, "no fabricated zero"):
            project_timeout_fields({})
        snapshots = defaultdict(dict)
        for rule in REFRESH_RULES:
            snapshots[rule.source_cluster][rule.source_field] = (
                False if rule.source_cluster == "DPS" else 1.0
            )
        first = REFRESH_RULES[0]
        for bad in (True, None, float("nan")):
            snapshots[first.source_cluster][first.source_field] = bad
            with self.assertRaises(ValueError):
                project_timeout_fields(snapshots)


class TranslatorSelectionTests(unittest.TestCase):
    def test_all_four_branches_patch_true_only_without_position_or_other_camera_off(
        self,
    ):
        for selection in TranslatorSelection:
            p = plan_translator_selection(selection)
            self.assertEqual(
                len(p.assignments), 2 if selection is TranslatorSelection.LASER else 4
            )
            self.assertTrue(all(value is True for _, value in p.assignments))
            self.assertFalse(p.switches_other_cameras_off)
            self.assertFalse(p.commands_position)
            self.assertEqual([f.index for f in p.frames], [0, 1])
            delay_frame = 0 if selection is TranslatorSelection.LASER else 1
            delays = [
                (f.index, dict(e.arguments)["ms"])
                for f in p.frames
                for e in f.effects
                if e.operation == "Wait (ms)"
            ]
            self.assertEqual(delays, [(delay_frame, 2000)])
            self.assertEqual(p.frames[0].ui_patches[0].value, (7171459, 7171459))
            self.assertEqual(p.frames[1].ui_patches[0].value, (12171705, 12171705))

    def test_unknown_selection_and_unresolved_valid_path_fail_closed(self):
        with self.assertRaises(ValueError):
            plan_translator_selection(0)
        with self.assertRaises(ValueError):
            plan_load_toggle(True)


class OriginalNetlistProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = SUPERVISION / NETLIST_PATH
        cls.digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        cls.data = json.loads(path.read_text(encoding="utf-8"))
        cls.event = next(
            n for n in walk(cls.data["netlist"]["body"]) if n["uid"] == "5909"
        )
        cls.evidence = json.loads(
            (SUPERVISION / EVIDENCE_PATH).read_text(encoding="utf-8")
        )

    def test_parser_identity_and_no_execution(self):
        self.assertEqual(self.digest, NETLIST_SHA256)
        self.assertEqual(self.data["source_sha256"], SOURCE_VI_SHA256)
        self.assertEqual(
            self.data["parser_fingerprint"],
            "FA1E6520BFBC81C4EB841B94F7B1D22749D5FCF17516073F092BC20D291D75C8",
        )
        self.assertFalse(self.data["generated_execution"])
        self.assertFalse(self.data["behavioral_qualification"])

    def test_all_34_event_indices_link_real_bounded_modules(self):
        self.assertEqual(len(EVENT_MODEL_MODULES), 34)
        for event in EVENT_CASES:
            self.assertTrue(event.bounded_models)
            for name in event.bounded_models:
                self.assertIn(name, event.boundary)
                importlib.import_module("supervision_reconstruction.domain." + name)

    def test_frozen_loop_patch_and_additional_print_artifacts(self):
        path = SUPERVISION / "analysis/loop_ownership_evidence_20261004.json"
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            "85217B2482AE552795F2B447F33F48C0F7A407344BB923A56344B63750446C20",
        )
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["parser_fingerprint"], self.data["parser_fingerprint"])
        for row in receipt["artifacts"]:
            with self.subTest(path=row["path"]):
                self.assertEqual(
                    hashlib.sha256((SUPERVISION / row["path"]).read_bytes())
                    .hexdigest()
                    .upper(),
                    row["sha256"],
                )

    def test_four_autotune_sequences_owned_by_event30_loops(self):
        nodes = {n["uid"]: n for n in walk(self.event["frames"][30]["body"])}
        for stage in AutotuneStage:
            uid = str(stage.value[4])
            self.assertIn(uid, nodes)
            self.assertEqual([f["label"] for f in nodes[uid]["frames"]], ["0", "1"])
        root_uids = {n["uid"] for n in self.data["netlist"]["body"]}
        self.assertFalse(
            root_uids.intersection({str(s.value[4]) for s in AutotuneStage})
        )

    def test_autotune_connector_wires_match_all_eight_move_plans(self):
        nodes = {n["uid"]: n for n in walk(self.event["frames"][30]["body"])}
        for stage in AutotuneStage:
            for coordinate in (248.0, 252.0):
                p = project_autotune_iteration(
                    stage, coordinate, stop_motor=False, motor_error=False
                )
                node = nodes[str(p.move_intent.node_uid)]
                inputs = {int(x["terminal"]): x["net"] for x in node["inputs"]}
                args = dict(p.move_intent.arguments)
                self.assertEqual(inputs[args["true_connector_index"]]["bare"], "True")
                self.assertEqual(inputs[11]["bare"], "Voies NI1409")
                self.assertEqual(args["preceding_camera_channel"], stage.value[1])
                self.assertEqual(inputs[8]["bare"], str(stage.value[3]))

    def test_autotune_camera_operations_stay_in_original_frames(self):
        nodes = {n["uid"]: n for n in walk(self.event["frames"][30]["body"])}
        for channel in (2, 3):
            p = plan_autotune_camera_switch(channel, final_error=OK)
            sequence = nodes[str(p.sequence_uid)]
            for frame in p.frames:
                frame_nodes = {
                    n["uid"]: n for n in walk(sequence["frames"][frame.index]["body"])
                }
                for effect in frame.effects:
                    self.assertIn(str(effect.node_uid), frame_nodes)
                    self.assertEqual(
                        effect.operation, frame_nodes[str(effect.node_uid)]["name"]
                    )
                for patch in frame.ui_patches:
                    self.assertIn(str(patch.node_uid), frame_nodes)

    def test_translator_bundle_fields_match_original_wires(self):
        nodes = {n["uid"]: n for n in walk(self.event["frames"][3]["body"])}
        for selection in TranslatorSelection:
            p = plan_translator_selection(selection)
            uid = str(p.frames[0].effects[0].node_uid)
            assignments = tuple(
                (x["terminal"], x["net"]["bare"] == "True")
                for x in nodes[uid]["inputs"]
                if x["terminal"] != "1"
            )
            self.assertEqual(assignments, p.assignments)

    def test_refresh_source_fields_and_nested_target_indices(self):
        nodes = {n["uid"]: n for n in walk(self.event["frames"][0]["body"])}
        receipt = json.loads(
            (
                SUPERVISION / "analysis/lvkit_eval/parser_release_20261003/00.json"
            ).read_text(encoding="utf-8")
        )
        types = (
            ET.parse(receipt["xml"][2]["path"])
            .getroot()
            .findall("VCTP/Section/TypeDesc")
        )

        def flatten(t, prefix=""):
            label = t.get("Label", "")
            path = prefix + label
            yield path
            if t.get("Type") == "Cluster":
                for child in t:
                    yield from flatten(types[int(child.get("TypeID"))], path + ".")

        for uid in {r.bundle_uid for r in REFRESH_RULES}:
            rules = [r for r in REFRESH_RULES if r.bundle_uid == uid]
            inputs = [x for x in nodes[str(uid)]["inputs"] if x["terminal"] != "1"]
            self.assertEqual(
                [x["net"]["terminal"] for x in inputs], [r.source_field for r in rules]
            )
            schema = next(
                t
                for t in types
                if t.get("Type") == "Cluster"
                and t.get("Label") == rules[0].target_cluster
            )
            paths = [
                p for child in schema for p in flatten(types[int(child.get("TypeID"))])
            ]
            indices = self.evidence["nodes"][str(uid)]["term_field_indices"][2:]
            self.assertEqual(
                [paths[int(i)] for i in indices], [r.target_path for r in rules]
            )
            for rule in rules:
                fields = self.evidence["original_cluster_schemas"][rule.source_cluster]
                field = next(f for f in fields if f.get("Label") == rule.source_field)
                self.assertEqual(
                    field["Type"],
                    "Boolean" if rule.source_cluster == "DPS" else "NumFloat64",
                )


if __name__ == "__main__":
    unittest.main()
