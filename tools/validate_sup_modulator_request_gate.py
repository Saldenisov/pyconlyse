"""Check saved Supervision Page Modulateur gate and DPS wires, offline.

Usage: python tools/validate_sup_modulator_request_gate.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
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

COMMANDS = (
    (22, "32208", 2, "33493"),
    (23, "32239", 3, "33501"),
    (46, "54314", 4, "60109"),
    (47, "57159", 5, "60114"),
    (48, "57855", 6, "60117"),
    (49, "57860", 7, "60120"),
    (50, "57863", 8, "60123"),
    (51, "57866", 9, "60126"),
    (52, "57869", 10, "60129"),
    (53, "57872", 11, "60132"),
    (21, "57875", 12, "60135"),
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


def wire(signals: list[set[str]], source: str, target: str) -> None:
    require(any({source, target} <= group for group in signals),
            f"direct wire {source}->{target} absent")


def field(mux: ET.Element, terminal_uid: str) -> int:
    matches = [term for term in mux.findall("termList/*") if term.get("uid") == terminal_uid]
    require(len(matches) == 1, f"terminal {terminal_uid} absent from mux {mux.get('uid')}")
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
    frames = event.find("diagramList")
    require(frames is not None and len(frames) == 34, "root event frame count changed")
    page_event = frames[18]
    require(page_event.get("uid") == "30817", "Page Modulateur event frame changed")
    refs = {ref.findtext("termList/*/dco/paramIdx")
            for ref in page_event.iter() if ref.get("class") == "gRef"}
    require(refs == {"176", "184"}, f"event local-reference set changed: {refs}")
    source_ref = unique(root, "gRef", "30929")
    require(source_ref in page_event.iter()
            and source_ref.findtext("termList/*/dco/paramIdx") == "176",
            "DPS gate source local changed")
    for uid, primitive_id in (("43109", "1169"), ("43129", "1910")):
        primitive = unique(root, "prim", uid)
        require(primitive in page_event.iter()
                and primitive.findtext("primResID") == primitive_id,
                f"DPS gate primitive {uid} changed")
    outer_signals = peers(page_event)
    for source, target in (
        ("30933", "43120"),  # local DPS -> Cluster To Array
        ("43114", "43328"),  # Boolean array -> Or Array Elements
        ("43229", "30951"),  # any DPS request -> case selector
        ("30915", "30959"),  # event NewVal cluster -> case tunnel
    ):
        wire(outer_signals, source, target)
    selector = unique(root, "select", "30946")
    require(selector in page_event.iter(), "DPS request case moved")
    ranges = selector.find("SelectRangeArray32")
    require(ranges is not None and [
        (case.findtext("start"), case.findtext("diagramIdx"))
        for case in ranges
    ] == [("0", "0"), ("1", "1")], "case polarity changed")
    false_frame, true_frame = selector.find("diagramList")
    require(false_frame.get("uid") == "31001"
            and true_frame.get("uid") == "42181", "request branch frames changed")
    require(not any(node.get("class") == "sharedVariableDynamicWrite"
                    for node in true_frame.iter()),
            "busy branch now writes a shared variable")
    source_mux = unique(root, "nMux", "32126")
    target_mux = unique(root, "nMux", "33466")
    dps_base = unique(root, "gRef", "33453")
    writer = unique(root, "sharedVariableDynamicWrite", "33792")
    require(all(node in false_frame.iter() for node in
                (source_mux, target_mux, dps_base, writer)),
            "DPS request wire nodes moved")
    require(dps_base.findtext("termList/*/dco/paramIdx") == "176",
            "DPS request base local changed")
    branch_signals = peers(false_frame)
    wire(branch_signals, "30966", "32188")  # NewVal cluster -> source mux
    wire(branch_signals, "33461", "33472")  # local DPS base -> target mux
    wire(branch_signals, "33472", "33954")  # built DPS -> PSP write data
    wire(branch_signals, "31469", "33804")  # literal PSP URL -> writer
    uri_terms = [term for term in false_frame.findall("nodeList/*/termList/*")
                 if term.get("uid") == "31469"]
    require(len(uri_terms) == 1, "DPS URI constant absent")
    uri_hex = uri_terms[0].findtext("dco/ConstValue")
    require(uri_hex is not None and bytes.fromhex(uri_hex)[4:].decode("ascii") ==
            "ni.var.psp://localhost/SUPERVISION/DPS", "DPS PSP URI changed")
    page_names = cluster_fields(main, "Page Modulateur")
    dps_names = cluster_fields(main, "DPS")
    require(len(page_names) == 59 and len(dps_names) == 29,
            "Page Modulateur or DPS schema size changed")
    lines = []
    for source_index, source_uid, target_index, target_uid in COMMANDS:
        require(field(source_mux, source_uid) == source_index,
                f"Page Modulateur field {source_uid} changed")
        require(field(target_mux, target_uid) == target_index,
                f"DPS field {target_uid} changed")
        wire(branch_signals, source_uid, target_uid)
        lines.append(f"Page Modulateur[{source_index}] {page_names[source_index]} -> "
                     f"DPS[{target_index}] {dps_names[target_index]}")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    for line in validate(args.source_export_zip):
        print(line)
    print("PASS: Page Modulateur event 18 DPS request gate and 11 direct wires")


if __name__ == "__main__":
    main()
