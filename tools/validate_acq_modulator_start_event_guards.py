"""Check five saved ACQ modulator start-event branch shapes, offline only.

Usage: python tools/validate_acq_modulator_start_event_guards.py SOURCE_EXPORT_ZIP
This does not inspect subVI internals or operate hardware.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
BDHB_SHA256 = "36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB"

# ACQ event index, event diagram, event-data node, selector, False frame,
# True frame, ordered sequence, expected frame count, NewVal terminal,
# selector terminal. Every tuple is checked against the saved raw graph.
START_EVENTS = (
    (5, "34531", "34547", "34571", "34585", "34591", "34597", 10, "34564", "34573"),
    (12, "37991", "38007", "38031", "38045", "38051", "38057", 7, "38024", "38033"),
    (13, "23143", "23924", "24272", "24286", "24292", "24303", 8, "24263", "24274"),
    (14, "35942", "35958", "35982", "35996", "36002", "36008", 8, "35975", "35984"),
    (15, "40079", "40097", "40121", "40135", "40141", "40147", 8, "40114", "40123"),
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise AssertionError(reason)


def checked_root(path: Path) -> ET.Element:
    require(path.is_file(), f"source archive absent: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(actual == ARCHIVE_SHA256, f"unexpected archive SHA-256: {actual}")
    with ZipFile(path) as archive:
        require(set(archive.namelist()) == {"vi_BDHb.xml", "vi.xml"},
                "archive members changed")
        diagram = archive.read("vi_BDHb.xml")
    require(hashlib.sha256(diagram).hexdigest().upper() == BDHB_SHA256,
            "block diagram export hash changed")
    return ET.fromstring(diagram)


def unique(root: ET.Element, klass: str, uid: str) -> ET.Element:
    matches = root.findall(f".//*[@class='{klass}'][@uid='{uid}']")
    require(len(matches) == 1, f"expected one {klass} UID {uid}, got {len(matches)}")
    return matches[0]


def validate(path: Path) -> list[str]:
    root = checked_root(path)
    runtime = unique(root, "eventStruct", "43")
    frames = runtime.find("diagramList")
    require(frames is not None and len(frames) == 26,
            "runtime event frame count changed")
    lines = []
    for (index, diagram_uid, event_data_uid, selector_uid, false_uid,
         true_uid, sequence_uid, sequence_size, value_uid, selector_term_uid) in START_EVENTS:
        diagram = frames[index]
        require(diagram.get("uid") == diagram_uid,
                f"event {index} diagram changed")
        refs = {ref.findtext("termList/*/dco/paramIdx")
                for ref in diagram.iter() if ref.get("class") == "gRef"}
        require(refs == {"15", "35", "36", "44"},
                f"event {index} local-reference set changed: {refs}")
        selectors = [node for node in diagram.iter() if node.get("class") == "select"]
        require(len(selectors) == 1 and selectors[0].get("uid") == selector_uid,
                f"event {index} has another/moved case selector")
        primitive_ids = {node.findtext("primResID") for node in diagram.iter()
                         if node.get("class") == "prim"}
        require(primitive_ids == {"1302"},
                f"event {index} root primitive set changed: {primitive_ids}")
        selector = selectors[0]
        event_data = unique(root, "eventDataNode", event_data_uid)
        require(event_data in diagram.iter(), f"event {index} data node moved")
        event_value = [term for term in event_data.findall("termList/*")
                       if term.get("uid") == value_uid]
        require(len(event_value) == 1 and event_value[0].findtext("dco/i") == "6",
                f"event {index} NewVal terminal changed")
        require(any({value_uid, selector_term_uid} <=
                    {term.get("uid") for term in signal.findall("termList/*")}
                    for signal in diagram.findall("signalList/*")),
                f"event {index} NewVal-to-case wire absent")
        ranges = selector.find("SelectRangeArray32")
        require(ranges is not None and [
            (case.findtext("start"), case.findtext("diagramIdx"))
            for case in ranges
        ] == [("0", "0"), ("1", "1")], f"event {index} case polarity changed")
        case_frames = selector.find("diagramList")
        require(case_frames is not None and len(case_frames) == 2,
                f"event {index} case count changed")
        false_frame, true_frame = case_frames
        require(false_frame.get("uid") == false_uid
                and len(false_frame.find("zPlaneList")) == 0,
                f"event {index} False arm no longer empty")
        require(true_frame.get("uid") == true_uid,
                f"event {index} True arm changed")
        sequence = unique(root, "sequence", sequence_uid)
        require(sequence in true_frame.iter()
                and len(sequence.find("diagramList")) == sequence_size,
                f"event {index} True procedure sequence changed")
        lines.append(f"ACQ event {index}: NewVal=True -> {sequence_size} frames; "
                     "no direct C4 input local or nested case in root handler")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: five modulator start-event root branch shapes")


if __name__ == "__main__":
    main()
