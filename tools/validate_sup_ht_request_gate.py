"""Check saved Page HT request-gate wires; never run a VI or write PSP.

Usage: python tools/validate_sup_ht_request_gate.py SOURCE_EXPORT_ZIP
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ARCHIVE_SHA256 = "68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2"
BDHB_SHA256 = "36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93"
MAIN_SHA256 = "9EB636BC9FBD8596938A5F518DE06BA1C23D21FEF2556D13B1D44D46E54E2FA6"

ARROWS = (
    (15, "40839", "40932"), (13, "40849", "40941"),
    (14, "40858", "40950"), (16, "40867", "40959"),
    (21, "42117", "48621"), (19, "42122", "48639"),
    (20, "42125", "48648"), (22, "47590", "48657"),
)
COMMANDS = (
    (10, "38960", 15, "38981"),  # Marche HT
    (11, "38963", 17, "38984"),  # Arrêt HT
    (9, "19618", 16, "42706"),  # Reset HT
    (25, "19624", 18, "42711"),  # Marche pulse MOD
    (24, "19628", 19, "42714"),  # Arrêt pulse MOD
)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise AssertionError(reason)


def checked_archive(path: Path) -> tuple[ET.Element, ET.Element]:
    require(path.is_file(), f"source archive absent: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(actual == ARCHIVE_SHA256, f"unexpected archive SHA-256: {actual}")
    with ZipFile(path) as archive:
        require(set(archive.namelist()) == {"vi_BDHb.xml", "vi.xml"},
                "archive members changed")
        diagram = archive.read("vi_BDHb.xml")
        types = archive.read("vi.xml")
    require(hashlib.sha256(diagram).hexdigest().upper() == BDHB_SHA256,
            "diagram export hash changed")
    require(hashlib.sha256(types).hexdigest().upper() == MAIN_SHA256,
            "type export hash changed")
    return ET.fromstring(diagram), ET.fromstring(types)


def unique(root: ET.Element, klass: str, uid: str) -> ET.Element:
    matches = root.findall(f".//*[@class='{klass}'][@uid='{uid}']")
    require(len(matches) == 1, f"expected one {klass} UID {uid}, got {len(matches)}")
    return matches[0]


def peers(diagram: ET.Element) -> list[set[str]]:
    return [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in diagram.findall("signalList/*")
    ]


def wire(diagram_peers: list[set[str]], source: str, target: str) -> None:
    require(any({source, target} <= group for group in diagram_peers),
            f"direct wire {source}->{target} absent")


def field(mux: ET.Element, terminal_uid: str) -> int:
    matches = [term for term in mux.findall("termList/*") if term.get("uid") == terminal_uid]
    require(len(matches) == 1, f"terminal {terminal_uid} absent in mux {mux.get('uid')}")
    return int(matches[0].findtext("dco/i", default="-1"))


def cluster_fields(main: ET.Element, label: str) -> list[str]:
    section = main.find("VCTP/Section")
    require(section is not None, "VCTP type section absent")
    flat = [item for item in section if item.tag == "TypeDesc" and item.get("Type")]
    matches = [item for item in flat if item.get("Type") == "Cluster" and item.get("Label") == label]
    require(len(matches) == 1, f"expected one {label} cluster")
    return [flat[int(item.get("TypeID", "-1"))].get("Label", "") for item in matches[0]]


def validate(path: Path) -> list[str]:
    root, main = checked_archive(path)
    return validate_tree(root, main)


def validate_tree(root: ET.Element, main: ET.Element) -> list[str]:
    """Check the graph; callers must independently pin their source identity."""
    event = unique(root, "eventStruct", "5909")
    event_frames = event.find("diagramList")
    require(event_frames is not None and len(event_frames) == 34,
            "root event frame count changed")
    frame = event_frames[15]
    require(frame.get("uid") == "38707", "Page HT event frame 15 changed")
    refs = {ref.findtext("termList/*/dco/paramIdx")
            for ref in frame.iter() if ref.get("class") == "gRef"}
    require(refs == {"168", "176", "184", "24", "25"},
            f"Page HT event local refs changed: {sorted(refs)}")
    top = peers(frame)
    for source, target in (
        ("38743", "40829"),  # event NewVal -> Page HT unbundle
        ("38753", "40782"),  # local pending DPS -> Cluster To Array
        ("40773", "40807"),  # Boolean array -> Or Array Elements
        ("40798", "40895"),  # pending-command aggregate -> Or
        ("40923", "40986"),  # adjustment array -> Or Array Elements
        ("40977", "40905"),  # adjustment aggregate -> Or
        ("40885", "38760"),  # aggregate -> case selector
    ):
        wire(top, source, target)
    for uid, klass, primitive_id in (
        ("40765", "prim", "1169"),  # Cluster To Array
        ("40791", "prim", "1910"),  # Or Array Elements
        ("40970", "prim", "1910"),
        ("40877", "prim", "1062"),  # Or
    ):
        node = unique(root, klass, uid)
        require(node in frame.iter() and node.findtext("primResID") == primitive_id,
                f"gate primitive {uid} changed")
    pending = unique(root, "gRef", "38750")
    require(pending in frame.iter()
            and pending.findtext("termList/*/dco/paramIdx") == "176",
            "pending request local reference changed")
    arrows = unique(root, "nMux", "40816")
    require(arrows in frame.iter(), "Page HT adjustment unbundle moved")
    for index, source, target in ARROWS:
        require(field(arrows, source) == index, f"arrow field {source} changed")
        wire(top, source, target)
    gate = unique(root, "select", "38758")
    require(gate in frame.iter(), "Page HT branch selector moved")
    cases = gate.find("SelectRangeArray32")
    require(cases is not None and [
        (case.findtext("start"), case.findtext("end"), case.findtext("diagramIdx"))
        for case in cases
    ] == [("0", "0", "0"), ("1", "1", "1")], "Boolean case order changed")
    false_frame = gate.find("diagramList")[0]
    require(false_frame.get("uid") == "38901", "DPS branch is no longer case 0")
    branch_peers = peers(false_frame)
    source_mux = unique(root, "nMux", "38955")
    target_mux = unique(root, "nMux", "38974")
    writer = unique(root, "sharedVariableDynamicWrite", "38989")
    pending_base = unique(root, "gRef", "38967")
    require(all(node in false_frame.iter() for node in
                (source_mux, target_mux, writer, pending_base)),
            "DPS source/target/write node moved from false branch")
    require(pending_base.findtext("termList/*/dco/paramIdx") == "176",
            "DPS branch base is no longer local pending request cluster")
    wire(branch_peers, "38970", "38976")  # local DPS base -> bundled cluster
    wire(branch_peers, "38976", "39003")  # built DPS cluster -> PSP write data
    page_names = cluster_fields(main, "Page HT")
    dps_names = cluster_fields(main, "DPS")
    require(len(page_names) == 28 and len(dps_names) == 29,
            "Page HT or DPS cluster field count changed")
    lines = []
    for source_index, source_uid, target_index, target_uid in COMMANDS:
        require(field(source_mux, source_uid) == source_index,
                f"Page HT field {source_uid} changed")
        require(field(target_mux, target_uid) == target_index,
                f"DPS field {target_uid} changed")
        wire(branch_peers, source_uid, target_uid)
        lines.append(f"Page HT[{source_index}] {page_names[source_index]} -> "
                     f"DPS[{target_index}] {dps_names[target_index]}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Page HT event 15 request gate and five DPS forwarding wires")


if __name__ == "__main__":
    main()
