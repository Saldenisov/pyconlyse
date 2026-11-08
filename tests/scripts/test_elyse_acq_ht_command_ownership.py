"""Original C9 writer/reader census and discriminating source mutations."""

import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from validate_acq_ht_command_ownership import (
    C9_REFERENCES,
    LIFECYCLE_FRAMES,
    validate_phase_ownership,
    validate_trees,
)
from validate_acq_modulator_start_event_guards import unique
from validate_acq_stop_ui_bindings import checked_trees


class HtCommandOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bd, cls.fp, cls.metadata = checked_trees()
        cls.compact = ET.Element("CheckedC9")
        for diagram in sorted({row[1] for row in C9_REFERENCES}):
            original = unique(cls.bd, "diag", diagram)
            frame = ET.SubElement(
                cls.compact, "Frame", {"class": "diag", "uid": diagram}
            )
            nodes = ET.SubElement(frame, "zPlaneList")
            signals = ET.SubElement(frame, "signalList")
            ports = {row[2] for row in C9_REFERENCES if row[1] == diagram}
            for row in C9_REFERENCES:
                if row[1] == diagram:
                    nodes.append(copy.deepcopy(unique(original, "gRef", row[0])))
            for signal in original.findall("signalList/*"):
                if ports & {t.get("uid") for t in signal.findall("termList/*")}:
                    signals.append(copy.deepcopy(signal))
        cls.compact_fp = ET.Element("CheckedControls")
        cls.compact_fp.append(copy.deepcopy(unique(cls.fp, "fPDCO", "7032")))
        cls.phases = ET.Element("CheckedLifecycle")
        outer = ET.SubElement(
            cls.phases, "Sequence", {"class": "sequence", "uid": "359"}
        )
        frames = ET.SubElement(outer, "diagramList")
        for uid in LIFECYCLE_FRAMES:
            frame = ET.SubElement(frames, "Frame", {"class": "diag", "uid": uid})
            ET.SubElement(frame, "zPlaneList")
        frames[1].find("zPlaneList").append(
            copy.deepcopy(unique(cls.bd, "gRef", "16414"))
        )
        for uid in ("47483", "59483", "20601", "203", "102"):
            loop = ET.SubElement(
                frames[2].find("zPlaneList"), "Loop", {"class": "whileLoop", "uid": uid}
            )
            if uid == "102":
                loop.append(copy.deepcopy(unique(cls.bd, "gRef", "10472")))
        frames[3].find("zPlaneList").append(
            copy.deepcopy(unique(cls.bd, "gRef", "11041"))
        )

    def check(self, bd=None, fp=None, metadata=None):
        return validate_trees(
            bd if bd is not None else self.compact,
            fp if fp is not None else self.compact_fp,
            metadata if metadata is not None else self.metadata,
        )

    def test_original_complete_typed_census_has_only_three_direct_writers(self):
        result = validate_trees(self.bd, self.fp, self.metadata)
        self.assertEqual(result["direct_writers"], ("10472", "11041", "16414"))
        self.assertEqual(result["direct_reads"], 10)
        self.assertFalse(result["physical_permission_proven"])

    def test_every_local_bank_direction_type_and_port_is_required(self):
        for uid, _, _, _, _, _ in C9_REFERENCES:
            for field in ("paramIdx", "objFlags", "typeDesc", "port"):
                changed = copy.deepcopy(self.compact)
                term = unique(changed, "gRef", uid).find("termList/*")
                if field == "port":
                    term.set("uid", "wrong")
                else:
                    dco = term.find("dco")
                    item = dco.find(field)
                    if item is None:
                        item = ET.SubElement(dco, field)
                    item.text = "1" if item.text is None else "wrong"
                with (
                    self.subTest(uid=uid, field=field),
                    self.assertRaises(AssertionError),
                ):
                    self.check(changed)

    def test_every_direct_wire_peer_and_diagram_is_required(self):
        for uid, diagram, port, _, _, _ in C9_REFERENCES:
            for field in ("peer", "owner"):
                changed = copy.deepcopy(self.compact)
                frame = unique(changed, "diag", diagram)
                if field == "owner":
                    frame.set("uid", "wrong")
                else:
                    signal = next(
                        s
                        for s in frame.findall("signalList/*")
                        if port in {t.get("uid") for t in s.findall("termList/*")}
                    )
                    next(
                        t for t in signal.findall("termList/*") if t.get("uid") != port
                    ).set("uid", "wrong")
                with (
                    self.subTest(uid=uid, field=field),
                    self.assertRaises(AssertionError),
                ):
                    self.check(changed)

    def test_extra_writer_or_typed_alias_is_not_ignored(self):
        for bank in ("12", "123"):
            changed = copy.deepcopy(self.compact)
            extra = copy.deepcopy(unique(changed, "gRef", "16414"))
            extra.set("uid", "additional")
            extra.find("termList/*/dco/paramIdx").text = bank
            changed.append(extra)
            with self.subTest(bank=bank), self.assertRaises(AssertionError):
                self.check(changed)

    def test_new_direct_c9_property_target_is_not_ignored(self):
        changed = copy.deepcopy(self.compact)
        prop = ET.SubElement(changed, "Property", {"class": "propNode", "uid": "extra"})
        ET.SubElement(prop, "ddo", {"uid": "6921"})
        with self.assertRaises(AssertionError):
            self.check(changed)

    def test_front_panel_link_and_ht_field_label_are_required(self):
        changed_fp = copy.deepcopy(self.compact_fp)
        unique(changed_fp, "fPDCO", "7032").find("ddo").set("uid", "wrong")
        with self.assertRaises(AssertionError):
            self.check(fp=changed_fp)
        changed = copy.deepcopy(self.metadata)
        labels = [
            n
            for n in changed.findall("VCTP/Section/TypeDesc")
            if n.get("Label") == "00 OUT00 b01 Cmd alimentation HT"
        ]
        self.assertTrue(labels)
        for node in labels:
            node.set("Label", "unrelated command")
        with self.assertRaises(AssertionError):
            self.check(metadata=changed)

    def test_original_phase_barrier_excludes_receiver_ramp_overlap(self):
        result = validate_phase_ownership(self.bd)
        self.assertEqual(result["runtime_loops_must_join_before_ramp"], 5)
        self.assertFalse(result["remote_receiver_overlaps_outer_ramp"])
        self.assertFalse(result["indirect_writers_or_new_vi_invocations_excluded"])

    def test_each_saved_lifecycle_phase_is_required(self):
        for uid in LIFECYCLE_FRAMES:
            changed = copy.deepcopy(self.phases)
            unique(changed, "diag", uid).set("uid", "wrong")
            with self.subTest(phase=uid), self.assertRaises(AssertionError):
                validate_phase_ownership(changed)

    def test_receiver_moved_into_stop_phase_is_rejected(self):
        changed = copy.deepcopy(self.phases)
        dispatcher = unique(changed, "whileLoop", "102")
        receiver = unique(changed, "gRef", "10472")
        dispatcher.remove(receiver)
        unique(changed, "diag", "41058").find("zPlaneList").append(receiver)
        with self.assertRaisesRegex(AssertionError, "lifecycle owner"):
            validate_phase_ownership(changed)

    def test_every_joined_runtime_loop_is_required(self):
        for uid in ("47483", "59483", "20601", "203", "102"):
            changed = copy.deepcopy(self.phases)
            nodes = unique(changed, "diag", "367").find("zPlaneList")
            nodes.remove(unique(changed, "whileLoop", uid))
            with self.subTest(loop=uid), self.assertRaises(AssertionError):
                validate_phase_ownership(changed)

    def test_additional_stop_phase_c9_writer_is_rejected(self):
        changed = copy.deepcopy(self.phases)
        extra = copy.deepcopy(unique(changed, "gRef", "11041"))
        extra.set("uid", "additional_stop_writer")
        unique(changed, "diag", "41058").find("zPlaneList").append(extra)
        with self.assertRaisesRegex(AssertionError, "another direct C9"):
            validate_phase_ownership(changed)


if __name__ == "__main__":
    unittest.main()
