import ast
import hashlib
import json
import runpy
import unittest
import xml.etree.ElementTree as ET
from dataclasses import FrozenInstanceError, replace
from itertools import product
from pathlib import Path

from supervision_reconstruction.domain import digital_command_events as model


class DigitalCommandEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.supervision = Path(__file__).resolve().parents[3]
        cls.proof_path = cls.supervision / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.proof_path.read_text(encoding="utf-8"))
        receipt = json.loads(
            (cls.supervision / cls.proof["artifacts"][0]["path"]).read_text(
                encoding="utf-8"
            )
        )
        cls.receipt = receipt
        cls.root = ET.parse(receipt["xml"][0]["path"]).getroot()
        cls.raw = {
            n.get("uid"): n for n in cls.root.iter() if n.get("uid") and n.get("class")
        }

    def pulse_plans(self):
        return [
            model.plan_faraday_position_change(s, True) for s in model.FaradayStation
        ] + [model.plan_laser_mirror_change(v) for v in (0, 1)]

    def writing_plans(self):
        return (
            self.pulse_plans()
            + [model.plan_slit_supply_change(v) for v in (0, 1)]
            + [model.plan_faraday_tab_change(0, en_states=(False, True, False))]
        )

    def test_three_faraday_true_branches_are_one_field_true_wait_false(self):
        for station in model.FaradayStation:
            with self.subTest(station=station):
                plan = model.plan_faraday_position_change(station, True)
                name = model.FARADAY_FIELDS[station - 1]
                self.assertEqual(plan.event_case_index, station + 8)
                self.assertEqual([f.index for f in plan.frames], [0, 1, 2])
                self.assertEqual(
                    [f.patches for f in plan.frames],
                    [((name, True),), (), ((name, False),)],
                )
                self.assertEqual([f.waits_ms for f in plan.frames], [(), (500,), ()])
                self.assertEqual(plan.frames[2].ui_assignments, model.FARADAY_UI_RESETS)
                self.assertEqual(plan.frames[0].ui_assignments, ())
                self.assertTrue(plan.dedicated_pulse_wait_frame)

    def test_faraday_false_is_a_noop_not_a_release_or_ui_reset(self):
        for station in model.FaradayStation:
            plan = model.plan_faraday_position_change(station, False)
            self.assertEqual(plan.frames, ())
            self.assertIsNone(plan.sequence_uid)
            self.assertFalse(plan.dedicated_pulse_wait_frame)
            self.assertFalse(plan.write_error_handlers_observed)

    def test_faraday_station_and_event_types_do_not_use_integer_truthiness(self):
        for station in (1, "1", False, None):
            with self.assertRaises(TypeError):
                model.plan_faraday_position_change(station, True)
        for value in (0, 1, "True", None, 0.0):
            with self.assertRaises(TypeError):
                model.plan_faraday_position_change(model.FaradayStation.ONE, value)

    def test_mirror_selectors_use_separate_en_hors_fields_and_1000ms_frame(self):
        for selector in (0, 1):
            plan = model.plan_laser_mirror_change(selector)
            self.assertEqual(plan.event_case_index, 8)
            self.assertEqual(
                plan.frames[0].patches, ((model.MIRROR_FIELDS[selector], True),)
            )
            self.assertEqual(plan.frames[1].waits_ms, (1000,))
            self.assertEqual(
                plan.frames[2].patches, ((model.MIRROR_FIELDS[selector], False),)
            )
            self.assertTrue(all(not f.ui_assignments for f in plan.frames))

    def test_mirror_does_not_clear_opposite_field_or_claim_an_interlock(self):
        for selector in (0, 1):
            plan = model.plan_laser_mirror_change(selector)
            original = {name: True for name in model.MIRROR_FIELDS}
            result = model.project_digital_frame(plan.frames[2], original)
            self.assertFalse(result[model.MIRROR_FIELDS[selector]])
            self.assertTrue(result[model.MIRROR_FIELDS[1 - selector]])
            self.assertEqual(original, {name: True for name in model.MIRROR_FIELDS})
            self.assertFalse(plan.establishes_physical_state)

    def test_unknown_selectors_do_not_invoke_motion_inducing_native_defaults(self):
        for function in (model.plan_laser_mirror_change, model.plan_slit_supply_change):
            for value in (-1, 2, 3, 65535, 10**100):
                with self.subTest(function=function.__name__, value=value):
                    with self.assertRaises(ValueError):
                        function(value)
        for function in (
            model.plan_laser_mirror_change,
            model.plan_slit_supply_change,
            model.plan_faraday_tab_change,
        ):
            for value in (True, False, "0", 1.0, None):
                with self.assertRaises(TypeError):
                    function(value)

    def test_slit_supply_is_not_a_pulse_and_retains_unordered_wait_color_frames(self):
        for value in (0, 1):
            plan = model.plan_slit_supply_change(value)
            self.assertEqual(plan.event_case_index, 5)
            self.assertEqual([f.index for f in plan.frames], [0, 1])
            self.assertEqual(
                plan.frames[0].patches, ((model.SLIT_SUPPLY_FIELD, bool(value)),)
            )
            self.assertEqual(plan.frames[1].patches, ())
            self.assertEqual([f.waits_ms for f in plan.frames], [(500,), (500,)])
            self.assertEqual(
                [f.ui_colors[0].values for f in plan.frames],
                [(7171459, 7171459), (12171705, 12171705)],
            )
            self.assertFalse(plan.dedicated_pulse_wait_frame)
            self.assertTrue(
                all(not f.operations_within_frame_serialized for f in plan.frames)
            )

    def test_three_nonstop_faraday_tabs_are_empty_without_reading_en_states(self):
        for value in (1, 2, 3):
            plan = model.plan_faraday_tab_change(value)
            self.assertEqual(plan.event_case_index, 4)
            self.assertEqual(plan.frames, ())
            self.assertIsNone(plan.sequence_uid)

    def test_faraday_arret_inverts_all_eight_incoming_en_combinations(self):
        for states in product((False, True), repeat=3):
            with self.subTest(states=states):
                plan = model.plan_faraday_tab_change(0, en_states=states)
                self.assertEqual(
                    plan.frames[0].patches,
                    tuple(zip(model.FARADAY_FIELDS, (not s for s in states))),
                )
                self.assertEqual(
                    plan.frames[1].patches,
                    tuple((name, False) for name in model.FARADAY_FIELDS),
                )
                self.assertEqual(
                    plan.frames[0].source_state_reads, model.FARADAY_EN_INPUTS
                )
                self.assertEqual(plan.frames[2].ui_assignments, model.FARADAY_UI_RESETS)
                self.assertEqual(
                    [f.waits_ms for f in plan.frames], [(500,), (), (500,)]
                )
                self.assertFalse(plan.dedicated_pulse_wait_frame)
                self.assertFalse(plan.exact_physical_pulse_width_proven)

    def test_arret_requires_real_boolean_inputs_and_rejects_unknown_tab_values(self):
        with self.assertRaises(ValueError):
            model.plan_faraday_tab_change(0)
        for states in (
            [True, False, True],
            (),
            (True,),
            (True, False, None),
            (1, 0, 1),
        ):
            with self.assertRaises(TypeError):
                model.plan_faraday_tab_change(0, en_states=states)
        for value in (-1, 4, 65535):
            with self.assertRaises(ValueError):
                model.plan_faraday_tab_change(value)

    def test_each_writing_frame_projects_a_fresh_snapshot_and_preserves_other_fields(
        self,
    ):
        plan = model.plan_faraday_position_change(model.FaradayStation.ONE, True)
        base = {name: False for name in model.FARADAY_FIELDS + model.MIRROR_FIELDS}
        first = model.project_digital_frame(plan.frames[0], base)
        self.assertTrue(first[model.FARADAY_FIELDS[0]])
        between = dict(first)
        between[model.FARADAY_FIELDS[1]] = True
        between[model.MIRROR_FIELDS[1]] = True
        final = model.project_digital_frame(plan.frames[2], between)
        self.assertFalse(final[model.FARADAY_FIELDS[0]])
        self.assertTrue(final[model.FARADAY_FIELDS[1]])
        self.assertTrue(final[model.MIRROR_FIELDS[1]])
        self.assertTrue(between[model.FARADAY_FIELDS[0]])
        self.assertFalse(base[model.FARADAY_FIELDS[0]])

    def test_projection_cannot_invent_missing_fields_or_coerce_unknown_readback(self):
        frame = model.plan_slit_supply_change(1).frames[0]
        with self.assertRaises(ValueError):
            model.project_digital_frame(frame, {})
        for value in (None, 0, "False"):
            with self.assertRaises(TypeError):
                model.project_digital_frame(frame, {model.SLIT_SUPPLY_FIELD: value})
        with self.assertRaises(TypeError):
            model.project_digital_frame(None, {})
        with self.assertRaises(TypeError):
            model.project_digital_frame(frame, [(model.SLIT_SUPPLY_FIELD, False)])

    def test_plans_are_immutable_and_cannot_opt_in_to_execution(self):
        for plan in self.writing_plans():
            self.assertFalse(plan.execution_allowed)
            self.assertTrue(plan.external_effects_blocked)
            self.assertFalse(plan.acknowledgement_observed)
            self.assertFalse(plan.establishes_physical_state)
            self.assertFalse(plan.later_frames_conditioned_on_success)
            self.assertEqual(plan.base_cluster, "C5_OUT_DIO96")
            self.assertEqual(plan.connection_refnum, 47)
            self.assertEqual(plan.psp_url, model.PSP_URL)
            self.assertTrue(plan.write_error_handlers_observed)
            for frame in plan.frames:
                self.assertEqual(
                    frame.fresh_local_cluster_read_required,
                    frame.write_evidence is not None,
                )
            with self.assertRaises(FrozenInstanceError):
                plan.frames = ()
            with self.assertRaises(ValueError):
                replace(plan, execution_allowed=True)

    def test_pinned_source_xml_receipt_descriptions_and_48_native_images(self):
        self.assertEqual(
            hashlib.sha256(self.proof_path.read_bytes()).hexdigest().upper(),
            model.EVIDENCE_SHA256,
        )
        self.assertEqual(self.proof["source_vi_sha256"], model.SOURCE_VI_SHA256)
        self.assertEqual(len(self.proof["artifacts"]), 56)
        images = [a for a in self.proof["artifacts"] if a["path"].endswith(".png")]
        self.assertEqual(len(images), 48)
        for a in self.proof["artifacts"]:
            path = self.supervision / a["path"]
            with self.subTest(path=a["path"]):
                self.assertEqual(path.stat().st_size, a["bytes"])
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest().upper(), a["sha256"]
                )

    def test_evidence_builder_reproduces_receipt_without_a_converter_or_vi(self):
        builder = runpy.run_path(
            str(self.supervision / "analysis/build_digital_event_evidence.py")
        )
        self.assertEqual(builder["build_evidence"](), self.proof)
        self.assertFalse(self.proof["generation_or_vi_execution"])
        self.assertFalse(self.proof["full_vi_qualification"])
        self.assertEqual(self.proof["global_png_mapping_status"], "UNMAPPED")
        self.assertEqual(
            [e["index"] for e in self.proof["events"]], [4, 5, 8, 9, 10, 11]
        )
        self.assertTrue(all(e["old_contexts_agree"] for e in self.proof["events"]))

    def test_original_wires_connect_patches_to_both_local_and_psp_then_error_handler(
        self,
    ):
        nodes = self.proof["nodes"]
        for plan in self.writing_plans():
            frames = self.proof["scopes"][str(plan.sequence_uid)]["frames"]
            for frame in plan.frames:
                if frame.write_evidence is None:
                    continue
                with self.subTest(event=plan.event_case_index, frame=frame.index):
                    e = frame.write_evidence
                    bundle, read, local, psp, error = [
                        nodes[str(uid)]
                        for uid in (
                            e.bundle_uid,
                            e.local_read_uid,
                            e.local_write_uid,
                            e.psp_write_uid,
                            e.error_handler_uid,
                        )
                    ]
                    self.assertEqual(read["stored_local_name"], model.BASE_CLUSTER)
                    self.assertEqual(local["stored_local_name"], model.BASE_CLUSTER)
                    self.assertFalse(read["stored_local_write"])
                    self.assertTrue(local["stored_local_write"])
                    self.assertEqual(
                        [i["terminal"] for i in bundle["inputs"]][1:],
                        [name for name, _ in frame.patches],
                    )
                    self.assertEqual(psp["inputs"][0]["net"]["bare"], "Refnum(47)")
                    wires = [set(w) for w in frames[frame.index]["wires"]]
                    required = (
                        {read["term_uids"][0], bundle["term_uids"][1]},
                        {
                            bundle["term_uids"][0],
                            local["term_uids"][0],
                            psp["term_uids"][4],
                        },
                        {psp["term_uids"][3], error["term_uids"][9]},
                    )
                    for terms in required:
                        self.assertTrue(any(terms <= wire for wire in wires), terms)

    def test_constant_patches_and_waits_match_both_saved_contexts(self):
        for plan in self.writing_plans():
            frames = self.proof["scopes"][str(plan.sequence_uid)]["frames"]
            for frame in plan.frames:
                if frame.write_evidence and not frame.source_state_reads:
                    inputs = self.proof["nodes"][str(frame.write_evidence.bundle_uid)][
                        "inputs"
                    ]
                    self.assertEqual(
                        [i["net"]["bare"] for i in inputs[1:]],
                        [str(value) for _, value in frame.patches],
                    )
                waits = [
                    self.proof["nodes"][uid]
                    for uid in frames[frame.index]["node_uids"]
                    if uid in self.proof["nodes"]
                    and self.proof["nodes"][uid]["old_description_name"] == "Wait (ms)"
                ]
                self.assertEqual(
                    tuple(int(n["inputs"][0]["net"]["bare"]) for n in waits),
                    frame.waits_ms,
                )

    def test_original_arret_select_wires_use_not_each_named_en_input(self):
        nodes = self.proof["nodes"]
        wires = [set(w) for w in self.proof["scopes"]["19355"]["frames"][0]["wires"]]
        bundle_terms = nodes["25219"]["term_uids"]
        for index, (read_uid, select_uid) in enumerate(
            (("31039", "87771"), ("81587", "67352"), ("82968", "68955"))
        ):
            read, select = nodes[read_uid], nodes[select_uid]
            self.assertEqual(read["stored_local_name"], model.FARADAY_EN_INPUTS[index])
            inputs = {i["terminal"]: i["net"]["bare"] for i in select["inputs"]}
            self.assertEqual((inputs["t_value"], inputs["f_value"]), ("False", "True"))
            self.assertTrue(
                any({read["term_uids"][0], select["term_uids"][2]} <= w for w in wires)
            )
            self.assertTrue(
                any(
                    {select["term_uids"][0], bundle_terms[index + 2]} <= w
                    for w in wires
                )
            )

    def test_native_empty_branches_and_explicit_default_boundaries_are_preserved(self):
        for uid in (53995, 77922, 57006):
            false_frame = self.raw[str(uid)].find("diagramList")[0]
            self.assertEqual(len(false_frame.find("zPlaneList")), 0)
            self.assertEqual(len(false_frame.find("signalList")), 0)
        faraday = self.raw["18778"].find("diagramList")
        for frame in list(faraday)[1:]:
            self.assertTrue(
                all(n.get("class") == "label" for n in frame.find("zPlaneList"))
            )
            self.assertEqual(len(frame.find("signalList")), 0)
        self.assertEqual(self.raw["76431"].findtext("SelectDefaultCase"), "01")
        # Remaining enum-type/default gap is retained, not advertised as repaired.
        by_uid = {c["uid"]: c for c in self.receipt["cases"]}
        for uid in ("18778", "60524"):
            self.assertIsNone(by_uid[uid]["type"])
            self.assertFalse(any(f["default"] for f in by_uid[uid]["frames"]))
        self.assertTrue(
            any(
                "enum selector type is None" in s
                for s in self.proof["known_parser_limits"]
            )
        )

    def test_each_original_event_uses_newval_not_oldval_to_select_its_branch(self):
        event = self.raw["5909"]
        for row in self.proof["events"]:
            frame = event.find("diagramList")[row["index"]]
            self.assertEqual(frame.get("uid"), row["event_diagram_uid"])
            data_uid = next(
                n.get("uid")
                for n in frame.find("zPlaneList")
                if self.proof["nodes"].get(n.get("uid"), {}).get("old_description_name")
                == "Event Data Node"
            )
            # Raw termList includes an aggregate slot before the visible fields.
            # Stored field index 5 is OldVal; index 6 is the wired NewVal.
            newval = next(
                t.get("uid")
                for t in self.raw[data_uid].find("termList")
                if t.findtext("dco/i") == "6"
            )
            selector = (
                self.raw[str(row["scope_uids"][0])].find("termList")[0].get("uid")
            )
            wires = [
                {n.get("uid") for n in s.find("termList")}
                for s in frame.find("signalList")
            ]
            self.assertTrue(any({newval, selector} <= wire for wire in wires))

    def test_both_legacy_color_values_match_native_property_node_inputs(self):
        for plan in self.writing_plans():
            for frame in plan.frames:
                if not frame.ui_colors:
                    continue
                original = self.proof["scopes"][str(plan.sequence_uid)]["frames"][
                    frame.index
                ]
                for color in frame.ui_colors:
                    node = next(
                        self.proof["nodes"][uid]
                        for uid in original["node_uids"]
                        if self.proof["nodes"].get(uid, {}).get("old_description_name")
                        == color.control
                    )
                    inputs = {i["terminal"]: i["net"]["bare"] for i in node["inputs"]}
                    self.assertEqual(
                        tuple(ast.literal_eval(inputs["Colors"]).values()), color.values
                    )

    def test_ui_resets_are_real_false_local_writes_not_physical_measurements(self):
        nodes = self.proof["nodes"]
        for plan in self.writing_plans():
            for frame in plan.frames:
                if not frame.ui_assignments:
                    continue
                raw_frame = self.proof["scopes"][str(plan.sequence_uid)]["frames"][
                    frame.index
                ]
                locals_written = {
                    nodes[uid]["stored_local_name"]: nodes[uid]
                    for uid in raw_frame["node_uids"]
                    if uid in nodes
                    and nodes[uid].get("stored_local_write")
                    and nodes[uid].get("stored_local_name") != model.BASE_CLUSTER
                }
                self.assertEqual(
                    set(locals_written), {name for name, _ in frame.ui_assignments}
                )
                terms = {n["term_uids"][0] for n in locals_written.values()}
                self.assertTrue(any(terms <= set(w) for w in raw_frame["wires"]))
                self.assertTrue(
                    all(
                        n["inputs"][0]["net"]["bare"] == "False"
                        for n in locals_written.values()
                    )
                )

    def test_domain_module_has_no_effectful_import_or_sleep_executor(self):
        tree = ast.parse(Path(model.__file__).read_text(encoding="utf-8"))
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(
            imports, {"__future__", "collections.abc", "dataclasses", "enum"}
        )
        self.assertFalse(any(isinstance(n, ast.Import) for n in ast.walk(tree)))
        forbidden = {"sleep", "open", "eval", "exec", "__import__"}
        self.assertFalse(
            any(
                isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in forbidden
                for n in ast.walk(tree)
            )
        )


if __name__ == "__main__":
    unittest.main()
