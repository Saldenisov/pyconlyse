"""Read-only terminal check of saved Supervision beam-line event guards.

Usage: python tools/validate_sup_beam_transfer_guard.py PATH_TO_0_SUP_ELYSE_BDHb.xml
No VI is opened, run, or saved; no PSP or NI connection is made.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path


EXPECTED_XML_SHA256 = "36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93"
EVENTS = (
    # event case, sequence, old/new comparator, outer cluster-to-array,
    # loop, inner cluster-to-array, Boolean-to-number, bitwise AND,
    # array maximum, >= comparator, guarded frame-1 case
    (19, "14098", "7720", "7734", "7742", "7791", "7783", "7799", "7836", "8425", "11830"),
    (20, "33504", "33658", "33669", "33677", "33747", "33739", "33755", "33815", "46437", "46564"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def node(root: ET.Element, uid: str) -> ET.Element:
    matches = [item for item in root.findall(f".//*[@uid='{uid}']") if item.get("class")]
    require(len(matches) == 1, f"expected one node UID {uid}, found {len(matches)}")
    return matches[0]


def term_uids(element: ET.Element) -> set[str]:
    terms = element.find("termList")
    return {term.get("uid", "") for term in terms} if terms is not None else set()


def enclosing_diagram(element: ET.Element, parents: dict[ET.Element, ET.Element]) -> ET.Element:
    current = parents.get(element)
    while current is not None and current.get("class") != "diag":
        current = parents.get(current)
    require(current is not None, f"no diagram for UID {element.get('uid')}")
    return current


def linked(a: ET.Element, b: ET.Element, parents: dict[ET.Element, ET.Element]) -> bool:
    diagram = enclosing_diagram(a, parents)
    if enclosing_diagram(b, parents) is not diagram:
        return False
    a_terms, b_terms = term_uids(a), term_uids(b)
    for signal in diagram.findall("signalList/*"):
        peers = {term.get("uid", "") for term in signal.findall("termList/*")}
        if peers & a_terms and peers & b_terms:
            return True
    return False


def connected_literal(
    target: ET.Element,
    expected: int,
    parents: dict[ET.Element, ET.Element],
) -> bool:
    diagram = enclosing_diagram(target, parents)
    for constant in diagram.findall("nodeList/*[@class='sRN']"):
        values = [item.text for item in constant.findall("termList/*/dco/ConstValue")]
        if any(value and int(value, 16) == expected for value in values):
            if linked(target, constant, parents):
                return True
    return False


def validate(path: Path) -> list[str]:
    require(path.is_file(), f"XML not found: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(digest == EXPECTED_XML_SHA256, f"unexpected BDHb SHA-256: {digest}")
    root = ET.parse(path).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    event = node(root, "5909")
    require(event.get("class") == "eventStruct", "UID 5909 is not an event structure")
    event_frames = event.find("diagramList")
    require(event_frames is not None, "event frame list absent")
    results = []
    for case, seq_uid, old_new, outer_cluster, loop, inner_cluster, to_number, mask, maximum, compare, guarded in EVENTS:
        event_frame = event_frames[case]
        sequence = node(root, seq_uid)
        require(sequence in event_frame.iter(), f"event {case} missing sequence {seq_uid}")
        frames = sequence.find("diagramList")
        require(frames is not None and len(frames) >= 3, f"event {case} missing frames")
        frame0, frame1, frame2 = frames[0], frames[1], frames[2]
        for uid in (old_new, outer_cluster, loop, maximum, compare):
            require(node(root, uid) in frame0.iter(), f"event {case} frame 0 missing UID {uid}")
        for uid in (inner_cluster, to_number, mask):
            require(node(root, uid) in node(root, loop).iter(), f"event {case} loop missing UID {uid}")
        for left, right in (
            (old_new, outer_cluster),
            (outer_cluster, loop),
            (inner_cluster, to_number),
            (to_number, mask),
            (loop, maximum),
            (maximum, compare),
        ):
            require(linked(node(root, left), node(root, right), parents), f"event {case}: {left}->{right} not wired")
        require(connected_literal(node(root, mask), 1937, parents), f"event {case}: mask 1937 not wired")
        require(connected_literal(node(root, compare), 128, parents), f"event {case}: threshold 128 not wired")
        select = node(root, guarded)
        require(select in frame1.iter(), f"event {case}: frame-1 guard absent")
        branches = select.find("diagramList")
        require(branches is not None and len(branches) == 2, f"event {case}: guard is not Boolean")
        require(not branches[0].findall("zPlaneList/*"), f"event {case}: False branch not empty")
        require(bool(branches[1].findall("zPlaneList/*")), f"event {case}: True branch empty")
        writes = frame2.findall("zPlaneList/*[@class='sharedVariableDynamicWrite']")
        require(len(writes) == 4, f"event {case}: expected four unguarded PSP writes, got {len(writes)}")
        results.append(f"event {case}: mask=1937 threshold=128, frame-1 guarded; frame-2 PSP writes=4")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    args = parser.parse_args()
    for line in validate(args.bdhb_xml):
        print(line)
    print("PASS: static Supervision beam-line guard transfer")


if __name__ == "__main__":
    main()
