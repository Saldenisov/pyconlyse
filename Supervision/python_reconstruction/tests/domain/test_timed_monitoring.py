import hashlib
import itertools
import json
import math
import unittest
import xml.etree.ElementTree as ET
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from supervision_reconstruction.domain import journal
from supervision_reconstruction.domain import timed_monitoring as model
from supervision_reconstruction.domain.radioprotection import (
    EpcState,
    RadioprotectionGraph,
)

SUPERVISION = Path(__file__).resolve().parents[3]


class TimedMonitoringTests(unittest.TestCase):
    def good(self):
        return model.MonitoringCounters(9, 9, 0, 0, 9, 5)

    def test_six_counter_deltas_are_raw_subtractions(self):
        current = model.MonitoringCounters(12, 24, 36, 48, 60, 72)
        previous = model.MonitoringCounters(2, 4, 6, 8, 10, 12)
        self.assertEqual(
            model.project_counter_deltas(current, previous),
            model.MonitoringCounters(10, 20, 30, 40, 50, 60),
        )

    def test_counter_reset_is_negative_not_clamped_or_wrapped(self):
        self.assertEqual(
            model.project_counter_deltas(
                model.MonitoringCounters(0, 0, 0, 0, 0, 0),
                model.MonitoringCounters(100, 100, 100, 100, 100, 100),
            ).acq_auxiliary,
            -100,
        )

    def test_late_select_is_true_zero_false_one(self):
        self.assertEqual(model.project_late_numeric(True), 0)
        self.assertEqual(model.project_late_numeric(False), 1)
        for invalid in (0, 1, None, "False"):
            with self.assertRaises(TypeError):
                model.project_late_numeric(invalid)

    def test_monitoring_guard_all_32_boolean_combinations(self):
        for (
            good_aux,
            good_var,
            good_supvar,
            good_supevent,
            not_late,
        ) in itertools.product((False, True), repeat=5):
            counters = model.MonitoringCounters(
                9 if good_aux else 8,
                9 if good_var else 8,
                -123,
                -456,
                9 if good_supvar else 8,
                5 if good_supevent else 4,
            )
            result = model.project_monitoring_status(
                counters, finished_late_previous=not not_late
            )
            self.assertEqual(
                result.somme_monitoring,
                all((good_aux, good_var, good_supvar, good_supevent, not_late)),
            )
            self.assertFalse(result.is_physical_interlock)

    def test_strict_thresholds_exclude_equality(self):
        for name, threshold in (
            ("acq_auxiliary", 8),
            ("acq_variables", 8),
            ("sup_variables", 8),
            ("sup_events", 4),
        ):
            for value in (threshold - 0.001, threshold, threshold + 0.001):
                result = model.project_monitoring_status(
                    replace(self.good(), **{name: value}), finished_late_previous=False
                )
                self.assertEqual(result.somme_monitoring, value > threshold)

    def test_live_video_and_acquisition_event_deltas_do_not_gate_status(self):
        for value in (0, -100, float("nan"), float("inf")):
            result = model.project_monitoring_status(
                replace(self.good(), acq_events=value, sup_video=value),
                finished_late_previous=False,
            )
            self.assertTrue(result.somme_monitoring)
            self.assertTrue(dict(result.checks)["literal_video_2_gt_1"])

    def test_compared_nan_is_false_and_positive_infinity_is_not_sanitized(self):
        self.assertFalse(
            model.project_monitoring_status(
                replace(self.good(), sup_events=float("nan")),
                finished_late_previous=False,
            ).somme_monitoring
        )
        self.assertTrue(
            model.project_monitoring_status(
                replace(self.good(), sup_events=float("inf")),
                finished_late_previous=False,
            ).somme_monitoring
        )
        result = model.project_counter_deltas(
            replace(self.good(), sup_events=float("inf")),
            replace(self.good(), sup_events=float("inf")),
        )
        self.assertTrue(math.isnan(result.sup_events))

    def test_mean_request_order_is_bundle_order_not_execution_order(self):
        requests = model.plan_mean_requests(
            model.MonitoringCounters(11, 22, 33, 44, 55, 66),
            finished_late_previous=False,
        )
        self.assertEqual(
            tuple(request.node_uid for request in requests),
            model.TIME_CONTROL_MEAN_NODE_ORDER,
        )
        self.assertEqual(
            tuple(request.supplied_sample for request in requests),
            (1, 66, 55, 44, 22, 33, 11),
        )
        self.assertTrue(all(request.sample_length == 5 for request in requests))
        self.assertTrue(all(request.external_effects_blocked for request in requests))

    def test_mean_outputs_must_be_supplied_instead_of_invented(self):
        outputs = {
            uid: index + 0.25
            for index, uid in enumerate(model.TIME_CONTROL_MEAN_NODE_ORDER)
        }
        self.assertEqual(model.project_time_control(outputs), tuple(outputs.values()))
        with self.assertRaises(ValueError):
            model.project_time_control({})
        with self.assertRaises(TypeError):
            model.project_time_control(
                dict.fromkeys(model.TIME_CONTROL_MEAN_NODE_ORDER, True)
            )

    def test_radioprotection_caller_does_not_invent_helper_stored_output(self):
        graph = RadioprotectionGraph(1, 2, 3, 4)
        epc = EpcState(True, False, False, False, False, False, False)
        intent = model.plan_radioprotection_refresh(
            btim=11,
            graph_input=graph,
            somme_radioprotection=True,
            epc=epc,
            section_pressure=1e-7,
        )
        self.assertIs(intent.graph_input, graph)
        self.assertIs(intent.epc, epc)
        self.assertFalse(intent.helper_stored_output_supplied)
        self.assertTrue(intent.external_effects_blocked)

    def test_vacuum_graph_uses_seven_wired_sources_not_temperature_labels(self):
        readings = {
            name: float(index + 1)
            for index, name in enumerate(model.VACUUM_CHART_SOURCE_ORDER)
        }
        readings["T° Section"] = 999
        self.assertEqual(model.project_vacuum_chart(readings), (1, 2, 3, 4, 5, 6, 7))
        with self.assertRaises(ValueError):
            model.project_vacuum_chart({})

    def test_guide_hf_chart_and_empty_frame_remain_display_only(self):
        sample = model.plan_guide_hf_chart_sample(1e-6)
        self.assertEqual(sample.control, "Graphe déroulant")
        self.assertEqual(sample.source_field, "12 ACQ Vide PI Guide HF")
        self.assertEqual(sample.supplied_value, 1e-6)
        self.assertTrue(sample.external_effects_blocked)
        self.assertEqual(model.EMPTY_FRAME_INDEX, 6)
        self.assertEqual(model.FRAME_INDICES, tuple(range(9)))
        with self.assertRaises(FrozenInstanceError):
            sample.external_effects_blocked = False


class NonEventOriginalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = SUPERVISION / model.EVIDENCE_PATH
        cls.proof = json.loads(cls.path.read_text(encoding="utf-8"))
        receipt = json.loads(
            (
                SUPERVISION / "analysis/lvkit_eval/parser_release_20261003/00.json"
            ).read_text(encoding="utf-8")
        )
        root = ET.parse(receipt["xml"][0]["path"]).getroot()
        cls.raw = {
            n.get("uid"): n for n in root.iter() if n.get("class") and n.get("uid")
        }
        cls.frames = cls.proof["monitoring"]["frames"]

    def assert_wire(self, frame, endpoints):
        self.assertTrue(
            any(
                set(endpoints).issubset(wire)
                for wire in self.frames[frame]["original"]["wires"]
            ),
            (frame, endpoints),
        )

    def test_all_artifacts_and_both_model_proof_hashes_match(self):
        actual = hashlib.sha256(self.path.read_bytes()).hexdigest().upper()
        self.assertEqual(actual, model.EVIDENCE_SHA256)
        self.assertEqual(actual, journal.EVIDENCE_SHA256)
        for row in self.proof["artifacts"]:
            path = SUPERVISION / row["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest().upper(), row["sha256"]
            )
        self.assertFalse(self.proof["vi_or_generated_execution"])
        self.assertEqual(
            self.proof["error_code_database_scope"], "EXCLUDED_BY_USER_2026_10_04"
        )

    def test_original_journal_bytes_append_signature_and_prepend_wires(self):
        proof = self.proof["journal"]
        self.assertEqual(proof["constant_payload_hex_by_terminal_uid"]["100"], "0D0A")
        self.assertEqual(proof["constant_payload_hex_by_terminal_uid"]["455"], "")
        self.assertEqual(
            proof["writer_signature"][5]["Label"], "append to file? (new file:F)"
        )
        self.assertEqual(proof["writer_signature"][6]["Label"], "1D data")
        self.assertTrue(proof["writer_append_requested"])
        wires = [set(wire) for wire in proof["original_root"]["wires"]]
        for expected in (
            {"469", "168"},
            {"68", "171"},
            {"100", "174"},
            {"401", "213"},
            {"251", "222"},
        ):
            self.assertTrue(any(expected.issubset(wire) for wire in wires))
        self.assertEqual(proof["two_clock_nodes"], ["102", "127"])

    def test_original_timed_wrapper_exists_despite_export_orphaning(self):
        ancestors = self.proof["monitoring"]["original_ancestor_chain"]
        self.assertIn({"uid": "17671", "class": "timeLoop"}, ancestors)
        self.assertEqual(len(self.frames), 9)
        self.assertEqual(self.frames[6]["netlist_nodes"], [])

    def test_sequence_locals_link_counter_deltas_to_correct_thresholds(self):
        refs = self.proof["monitoring"]["sequence_local_terms"]
        for source_frame, source_terminal, slot, comparison_terminal in (
            (0, "35368", "9747", "39475"),
            (0, "32977", "10014", "41963"),
            (1, "16427", "16466", "134802"),
            (1, "16272", "34825", "38091"),
        ):
            self.assert_wire(source_frame, {source_terminal, refs[slot][source_frame]})
            self.assert_wire(4, {comparison_terminal, refs[slot][4]})

    def test_original_and_guard_preserves_inverted_late_input_and_video_literal(self):
        nodes = {n["uid"]: n for n in self.frames[4]["netlist_nodes"]}
        guard = nodes["15087"]
        self.assertEqual(guard["operation"], "and")
        inputs = {row["terminal"]: row for row in guard["inputs"]}
        self.assertTrue(inputs["1"]["inverted"])
        self.assertEqual(inputs["1"]["net"]["terminal"], "20")
        video = {
            row["terminal"]: row["net"]["terminal"] for row in nodes["38548"]["inputs"]
        }
        self.assertEqual(video, {"x": "2.0", "y": "1.0"})
        self.assert_wire(
            4, {"36671", self.proof["monitoring"]["sequence_local_terms"]["32635"][4]}
        )

    def test_mean_and_vacuum_bundle_order_matches_frozen_wires(self):
        self.assertEqual(
            tuple(self.proof["monitoring"]["time_control_mean_node_order"]),
            model.TIME_CONTROL_MEAN_NODE_ORDER,
        )
        mean_bundle = next(
            n for n in self.frames[3]["netlist_nodes"] if n["uid"] == "14228"
        )
        self.assertEqual(
            [
                row["net"]["occurrence"]
                for row in sorted(
                    mean_bundle["inputs"], key=lambda row: int(row["terminal"])
                )
            ],
            [15, 11, 12, 9, 13, 14, 10],
        )
        self.assertTrue(
            all(
                n["inputs"][1]["net"]["terminal"] == "5"
                for n in self.frames[3]["netlist_nodes"]
                if n["name"] == "Mean PtByPt.vi"
            )
        )
        vacuum_bundle = next(
            n for n in self.frames[7]["netlist_nodes"] if n["uid"] == "184055"
        )
        fields = [
            row["net"]["terminal"]
            for row in vacuum_bundle["inputs"]
            if row["terminal"] != "1"
        ]
        self.assertEqual(fields[1:], list(model.VACUUM_CHART_SOURCE_ORDER[1:]))


if __name__ == "__main__":
    unittest.main()
