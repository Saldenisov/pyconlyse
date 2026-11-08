"""Structural traversal tests, including flat sequence cells and nested loops."""

from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from build_acq_saved_diagram_census import call_names, diagram_rows


class OriginalDiagramCensusTests(unittest.TestCase):
    def make_diagram(self, parent, uid):
        frame = ET.SubElement(parent, "frame", {"class": "diag", "uid": uid})
        ET.SubElement(frame, "zPlaneList")
        ET.SubElement(frame, "signalList")
        return frame

    def make_root(self):
        document = ET.Element("document")
        root = ET.SubElement(document, "root", {"class": "diag", "uid": "1"})
        ET.SubElement(root, "zPlaneList")
        ET.SubElement(root, "signalList")
        return document, root

    def rows(self, document, metadata=None):
        return list(diagram_rows("test.vi", "source-hash", document,
                                 metadata if metadata is not None else ET.Element("metadata")))

    def test_unstructured_member_has_one_root_not_invented_frames(self):
        document, root = self.make_root()
        rows = self.rows(document)
        self.assertEqual([(r["owner_class"], r["diagram_uid"]) for r in rows], [("root", "1")])

    def test_stacked_sequence_and_for_body_both_traversed(self):
        document, root = self.make_root()
        sequence = ET.SubElement(root.find("zPlaneList"), "node", {"class": "sequence", "uid": "2"})
        frame = self.make_diagram(ET.SubElement(sequence, "diagramList"), "3")
        loop = ET.SubElement(frame.find("zPlaneList"), "node", {"class": "forLoop", "uid": "4"})
        self.make_diagram(ET.SubElement(loop, "diagramList"), "5")
        rows = self.rows(document)
        self.assertEqual([r["diagram_uid"] for r in rows], ["1", "3", "5"])
        self.assertEqual(rows[2]["scope_path"], "test.vi/root/sequence:2[0]/forLoop:4[0]")

    def test_flat_sequence_cells_not_skipped(self):
        document, root = self.make_root()
        sequence = ET.SubElement(root.find("zPlaneList"), "node", {"class": "flatSequence", "uid": "2"})
        cells = ET.SubElement(sequence, "sequenceList")
        for uid in ("3", "5"):
            cell = ET.SubElement(cells, "cell", {"class": "sequenceFrame", "uid": uid})
            self.make_diagram(ET.SubElement(cell, "diagramList"), str(int(uid) + 1))
        rows = self.rows(document)
        self.assertEqual([r["diagram_uid"] for r in rows], ["1", "4", "6"])
        self.assertEqual(rows[2]["frame_index"], 1)

    def test_comment_ancestry_preserved_without_active_arm_guess(self):
        document, root = self.make_root()
        disabled = ET.SubElement(root.find("zPlaneList"), "node", {"class": "commentNode", "uid": "2"})
        self.make_diagram(ET.SubElement(disabled, "diagramList"), "3")
        self.assertEqual(self.rows(document)[1]["ancestor_diagram_disable_uids"], "2")

    def test_never_promotes_structural_rows_to_behavioral_coverage(self):
        document, root = self.make_root()
        local = ET.SubElement(root.find("zPlaneList"), "node", {"class": "gRef", "uid": "2"})
        ET.SubElement(ET.SubElement(ET.SubElement(local, "termList"), "term"), "dco")
        row = self.rows(document)[0]
        self.assertFalse(row["local_names_resolved"])
        self.assertEqual(row["behavioral_coverage"], "UNREVIEWED")
        self.assertEqual(row["direct_local_param_indices"], "UNRESOLVED")

    def test_qualified_iuse_offset_maps_actual_uid(self):
        metadata = ET.fromstring('<metadata><IUVI><LinkSaveQualName><String>TPG 300.lvlib</String>'
            '<String>Close.vi</String></LinkSaveQualName><LinkOffsetList><Offset>0xEEC1</Offset>'
            '</LinkOffsetList></IUVI></metadata>')
        self.assertEqual(call_names(metadata), {"61121": "TPG 300.lvlib:Close.vi"})

    def test_conflicting_qualified_links_rejected(self):
        metadata = ET.fromstring('<metadata><IUVI><LinkSaveQualName><String>A.vi</String>'
            '</LinkSaveQualName><LinkOffsetList><Offset>0x1</Offset></LinkOffsetList></IUVI>'
            '<IUVI><LinkSaveQualName><String>B.vi</String></LinkSaveQualName><LinkOffsetList>'
            '<Offset>0x1</Offset></LinkOffsetList></IUVI></metadata>')
        with self.assertRaisesRegex(AssertionError, "conflicting call link"):
            call_names(metadata)


if __name__ == "__main__":
    unittest.main()
