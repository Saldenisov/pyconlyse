"""Source provenance and post-start fault fixtures; no plant interaction."""

import copy
import itertools
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import trace_acq_running_faults as trace


class RunningFaultResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.fp, cls.meta = trace.checked_trees()
        cls.c4 = trace.writer_census(cls.root, 15)
        cls.dps = trace.writer_census(cls.root, 36)

    def test_c4_and_dps_writer_censuses_include_whole_cluster_overwrites(self):
        self.assertEqual((self.c4["local_references"], self.c4["local_writers"]), (145, 68))
        self.assertEqual((self.dps["local_references"], self.dps["local_writers"]), (82, 28))
        self.assertEqual(self.c4["producer_classes"]["nMux"], 66)
        self.assertEqual(self.dps["producer_classes"]["nMux"], 26)
        self.assertEqual({r["writer"] for r in self.c4["whole_cluster_writers"]}, {"16132", "25478"})
        self.assertEqual({r["writer"] for r in self.dps["whole_cluster_writers"]}, {"31118", "87"})

    def test_stage_stop_lines_have_only_command_events_or_outer_controlled_stop(self):
        rows = trace.inspect_stop_sites(self.c4)
        self.assertEqual(len(rows), 18)
        self.assertEqual({r["field"] for r in rows}, {4, 6, 8})
        for field in (4, 6, 8):
            values = [r["value"] for r in rows if r["field"] == field]
            self.assertEqual(values.count(False), 3)
            self.assertEqual(values.count(True), 3)

    def test_all_fieldwise_dps_producers_clear_rather_than_raise_requests(self):
        self.assertTrue(all(r["value"] is False for r in self.dps["fields"]))
        self.assertEqual({r["field"] for r in self.dps["fields"] if r["field"] in (3, 5, 7, 11)},
                         {3, 5, 7, 11})

    def test_klystron_fault_inputs_have_no_other_local_consumer(self):
        census = trace.inspect_c4_consumers(self.root)
        self.assertEqual(len(census["references"]), 6)
        self.assertEqual(census["only_direct_local_unbundle_fields"], [19, 38])

    def test_all_16_raw_guard_combinations_have_nine_true_results(self):
        count = 0
        for a, b, c, d in itertools.product((False, True), repeat=4):
            c4, c3 = [False] * 64, [False] * 56
            c4[19], c4[38], c3[0], c3[6] = a, b, c, d
            result = trace.cooling_guard(enabled_arm=True, c4_snapshot=tuple(c4), c3_snapshot=tuple(c3))
            self.assertIs(result, (a or b) and (not c or not d))
            count += result
        self.assertEqual(count, 9)

    def test_klystron_water_vacuum_oil_and_current_bits_do_not_trigger_this_guard(self):
        for field in tuple(range(19)) + (20, 21, 22, 23):
            c4 = [False] * 64
            c4[field] = True
            with self.subTest(field=field):
                self.assertFalse(trace.cooling_guard(
                    enabled_arm=True, c4_snapshot=tuple(c4), c3_snapshot=(False,) * 56))

    def test_trip_does_not_write_stage_stop_card_or_clear_stage_ok(self):
        eps = tuple(i in (8, 14, 20, 26, 32) for i in range(77))
        dps = (True,) * 29
        snapshots = (
            {"10431": (True,) * 40}, {"13466": (False,) * 40}, {},
            {"22661": (True,) * 40}, {"30986": (False,) * 40},
            {"39289": eps, "39313": dps}, {"39444": (False,) * 29},
        )
        frames = [trace.trip_frame(i, snapshots=s) for i, s in enumerate(snapshots)]
        self.assertFalse(any(w.bank in (15, 30, 45) for f in frames for w in f.writes))
        outputs = {w.bank: w.data for w in frames[5].writes}
        self.assertEqual([outputs[44][i] for i in (8, 14, 20, 26, 32)], [True] * 5)
        self.assertEqual([outputs[36][i] for i in (3, 5, 7, 11)], [True] * 4)
        self.assertEqual([outputs[44][i] for i in (1, 2, 3, 5)], [True, False, False, True])

    def test_trip_card_intents_only_stop_canon_and_section_cooling(self):
        frames = [trace.trip_frame(i, snapshots={uid: (True,) * 40})
                  for i, uid in ((0, "10431"), (1, "13466"), (3, "22661"), (4, "30986"))]
        self.assertEqual([next(w for w in f.writes if w.bank == 17).data[bit]
                          for f, bit in zip(frames, (1, 1, 4, 4))], [False, True, False, True])
        self.assertTrue(all(w.bank in (17, 35) for f in frames for w in f.writes))

    def test_hidden_stage_stop_writer_is_rejected(self):
        root = copy.deepcopy(self.root)
        root.append(ET.fromstring('<n class="gRef" uid="HIDDEN"><termList>'
                                 '<t class="term" uid="HIDDEN_PORT"><objFlags>32768</objFlags>'
                                 '<dco><paramIdx>15</paramIdx></dco></t></termList></n>'))
        with self.assertRaisesRegex(AssertionError, "writer census"):
            trace.writer_census(root, 15)

    def test_dps_reset_cannot_silently_become_internal_stop_request(self):
        root = copy.deepcopy(self.root)
        owners, links = trace.graph_index(root)
        mux = trace.unique(root, "nMux", "24908")
        leaf = mux.findall("termList/*")[2]
        source = next(owners[p][1] for p in links[leaf.get("uid")][1]
                      if owners[p][0].get("class") == "sRN")
        source.find("dco/ConstValue").text = "01"
        with self.assertRaisesRegex(AssertionError, "True request producer"):
            trace.writer_census(root, 36)

    def test_stage_stop_cannot_gain_a_timeout_fault_path(self):
        census = copy.deepcopy(self.c4)
        next(r for r in census["fields"] if r["writer"] == "23331")["scope"] = (
            "sequence:359[2]/whileLoop:102[0]/eventStruct:43[0]/sequence:10111[3]")
        with self.assertRaisesRegex(AssertionError, "automatic path"):
            trace.inspect_stop_sites(census)

    def test_recovery_guard_is_not_an_automatic_restart(self):
        # An explicit example, not an assertion about electrical polarity:
        # once raw C4[19/38] are both False, False branch has no operations.
        self.assertFalse(trace.cooling_guard(enabled_arm=True,
                                            c4_snapshot=(False,) * 64,
                                            c3_snapshot=(False,) * 56))
        false_arm = trace.unique(self.root, "diag", "44189")
        self.assertEqual(list(false_arm.find("zPlaneList")), [])

    def test_saved_report_matches_source_and_retains_runtime_limits(self):
        result = trace.build(self.root, self.fp, self.meta)
        self.assertEqual(json.loads(trace.OUTPUT.read_text("utf-8")), result)
        self.assertFalse(result["observations"]["cooling"]["native"]["original_lv2012_runtime_equivalence"])
        for key in ("screen_used", "hardware_commands_sent", "vi_run_or_saved",
                    "runtime_code_changed", "qualifies_hardware_start"):
            self.assertFalse(result[key])


if __name__ == "__main__":
    unittest.main()
