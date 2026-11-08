"""Original-source qualification plus per-frame structural mutations."""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "tools"))

from build_acq_saved_diagram_census import call_names
from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import all_phases
from validate_acq_counter_procedures import (
    POLL_ROWS,
    STOP_ROWS,
    validate_counter_frame,
)
from validate_acq_linear_procedures import (
    EVENTS,
    ROWS,
    checked_vam,
    decode_frame,
    unique,
    validate_tree,
)
from validate_acq_magnet_conditioning import RAMPS, validate_ramp


class LinearProcedureSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.meta = checked_vam(
            REPOSITORY
            / "legacy/xp_acq_agent/data/source_exports/0_ACQ_ELYSE_XML_sha6fe8.zip"
        )
        cls.names = call_names(cls.meta)
        cls.context = {}
        for event in EVENTS:
            row = ROWS[event - 3]
            sequence = unique(cls.root, "sequence", row[12])
            internals = sequence.findall("termList/*/dco/termList/*")
            for index, frame in enumerate(sequence.findall("diagramList/*")):
                cls.context[frame.get("uid")] = (
                    internals[index].get("uid"),
                    1000 if event == 3 else 150,
                )

    def decode(self, uid):
        port, duration = self.context.get(uid, (None, None))
        return decode_frame(
            self.root,
            self.meta,
            unique(self.root, "diag", uid),
            port,
            duration,
            self.names,
        )

    def test_all_23_paths_match_independently_reviewed_plans(self):
        self.assertEqual(len(validate_tree(self.root, self.meta)), 23)

    def test_every_one_of_166_frames_rejects_added_unexplained_graph_content(self):
        for uid, _ in all_phases():
            frame = unique(self.root, "diag", uid)
            signal = frame.find("signalList/*/termList")
            extra = ET.Element("SL__arrayElement", uid="UNREVIEWED_FANOUT")
            if signal is None:
                signal = frame.find("zPlaneList")
                extra.set("class", "UNREVIEWED_OPERATION")
            signal.append(extra)
            try:
                with self.subTest(diagram=uid), self.assertRaises(AssertionError):
                    self.decode(uid)
            finally:
                signal.remove(extra)

    def test_every_frame_with_literal_detects_a_changed_value(self):
        for uid, expected in all_phases():
            frame = unique(self.root, "diag", uid)
            literal = frame.find("nodeList/*/termList/*/dco/ConstValue")
            if literal is None:
                continue
            before = literal.text
            literal.text = "0000" if before == "01" else "01"
            try:
                with self.subTest(diagram=uid):
                    try:
                        actual = self.decode(uid)
                    except (AssertionError, KeyError):
                        pass
                    else:
                        self.assertNotEqual(actual, expected)
            finally:
                literal.text = before

    def test_each_conditioning_body_rejects_a_missing_feedback_wire(self):
        for row in RAMPS:
            frame = unique(self.root, "diag", row[2])
            signals = frame.find("signalList")
            removed = signals[-1]
            signals.remove(removed)
            try:
                with self.subTest(body=row[2]), self.assertRaises(AssertionError):
                    validate_ramp(
                        self.root, self.meta, unique(self.root, "diag", row[0])
                    )
            finally:
                signals.append(removed)

    def test_conditioning_n_left_right_links_and_field_targets_are_not_interchangeable(
        self,
    ):
        for row in RAMPS:
            loop = unique(self.root, "forLoop", row[1])
            target = loop.findall("termList/*")[2].find("dco/termList/*")
            before = target.get("uid")
            target.set("uid", "UNREVIEWED_SR")
            try:
                with self.subTest(loop=row[1]), self.assertRaises(AssertionError):
                    validate_ramp(
                        self.root, self.meta, unique(self.root, "diag", row[0])
                    )
            finally:
                target.set("uid", before)

    def test_each_focal_error_destination_is_required(self):
        for uid in ("53835", "57312", "48404"):
            frame = unique(self.root, "diag", uid)
            signals = frame.find("signalList")
            removed = signals[0]
            signals.remove(removed)
            try:
                with self.subTest(cell=uid), self.assertRaises(AssertionError):
                    self.decode(uid)
            finally:
                signals.append(removed)

    def test_each_counter_poll_body_rejects_any_extra_or_removed_net(self):
        for row in STOP_ROWS:
            body = unique(self.root, "diag", row[4][1])
            signals = body.find("signalList")
            removed = signals[-1]
            signals.remove(removed)
            try:
                with self.subTest(body=row[4][1]), self.assertRaises(AssertionError):
                    validate_counter_frame(
                        self.root, self.meta, unique(self.root, "diag", row[0])
                    )
            finally:
                signals.append(removed)

    def test_done_property_threshold_or_stop_polarity_mutations_fail(self):
        for row in STOP_ROWS:
            body_uid = row[4][1]
            data = POLL_ROWS[body_uid]
            prop = unique(self.root, "propNode", data[5][0])
            greater = unique(self.root, "prim", data[2][0])
            loop = unique(self.root, "whileLoop", row[4][0])
            for target in (
                prop.find(".//PropItemCode"),
                greater.find("primResID"),
                loop.find("loopTestDCO/objFlags"),
            ):
                before = target.text
                target.text = "0"
                try:
                    with (
                        self.subTest(body=body_uid, field=target.tag),
                        self.assertRaises(AssertionError),
                    ):
                        validate_counter_frame(
                            self.root, self.meta, unique(self.root, "diag", row[0])
                        )
                finally:
                    target.text = before


if __name__ == "__main__":
    unittest.main()
