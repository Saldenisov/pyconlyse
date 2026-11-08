"""Read-only wire/type check of Supervision Page HT Boolean projection.

Usage: python tools/validate_sup_ht_status_projection.py SOURCE_EXPORT_ZIP
       python tools/validate_sup_ht_status_projection.py BDHB_XML MAIN_XML
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


BDHB_SHA256 = "36FC7E7C93FBA9A533D6B44609F9ED0F58FB3AA911E4F88B8A8648CD55124A93"
MAIN_SHA256 = "9EB636BC9FBD8596938A5F518DE06BA1C23D21FEF2556D13B1D44D46E54E2FA6"
ARCHIVE_SHA256 = "68920CD0C441D2F99037FBE60565AF12C80D2DC01EF421892F1D2D69AF9FE5D2"

# Source C4_IN_DIO96 index, source terminal UID, destination Page HT index,
# destination terminal UID. These terminals are direct peers in diagram 48064.
WIRES = (
    (35, "48132", 4, "48270"),
    (36, "49849", 5, "63012"),
    (46, "51073", 6, "63923"),
    (37, "52555", 8, "65241"),
    (32, "53701", 7, "67526"),
    (48, "57834", 27, "40106"),
    (49, "58919", 26, "40158"),
)
EXPECTED_NAMES = {
    4: "V HT",
    5: "I HT",
    6: "Radioprotection",
    7: "Relais 2 HT",
    8: "Relais 1 HT",
    26: "HT en défaut",
    27: "HT en marche",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def checked_root(path: Path, expected_sha256: str) -> ET.Element:
    require(path.is_file(), f"source absent: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(actual == expected_sha256, f"unexpected SHA-256 for {path}: {actual}")
    return ET.parse(path).getroot()


def checked_export_archive(path: Path) -> tuple[ET.Element, ET.Element]:
    require(path.is_file(), f"source archive absent: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    require(actual == ARCHIVE_SHA256, f"unexpected archive SHA-256: {actual}")
    with ZipFile(path) as archive:
        require(set(archive.namelist()) == {"vi_BDHb.xml", "vi.xml"},
                "archive export members changed")
        bdhb_bytes = archive.read("vi_BDHb.xml")
        main_bytes = archive.read("vi.xml")
    require(hashlib.sha256(bdhb_bytes).hexdigest().upper() == BDHB_SHA256,
            "block-diagram export hash changed")
    require(hashlib.sha256(main_bytes).hexdigest().upper() == MAIN_SHA256,
            "main type export hash changed")
    return ET.fromstring(bdhb_bytes), ET.fromstring(main_bytes)


def unique(root: ET.Element, klass: str, uid: str) -> ET.Element:
    matches = root.findall(f".//*[@class='{klass}'][@uid='{uid}']")
    require(len(matches) == 1, f"expected one {klass} UID {uid}, got {len(matches)}")
    return matches[0]


def field_index(mux: ET.Element, term_uid: str) -> int:
    matches = [term for term in mux.findall("termList/*") if term.get("uid") == term_uid]
    require(len(matches) == 1, f"terminal {term_uid} absent from mux {mux.get('uid')}")
    return int(matches[0].findtext("dco/i", default="-1"))


def cluster_fields(main: ET.Element, label: str) -> list[str]:
    section = main.find("VCTP/Section")
    require(section is not None, "VCTP/Section absent")
    flat = [item for item in section if item.tag == "TypeDesc" and item.get("Type")]
    matches = [item for item in flat if item.get("Type") == "Cluster" and item.get("Label") == label]
    require(len(matches) == 1, f"expected one {label} type")
    return [flat[int(child.get("TypeID", "-1"))].get("Label", "") for child in matches[0]]


def validate(source_path: Path, main_path: Path | None = None) -> list[str]:
    if main_path is None:
        root, main = checked_export_archive(source_path)
    else:
        root = checked_root(source_path, BDHB_SHA256)
        main = checked_root(main_path, MAIN_SHA256)
    sequence = unique(root, "sequence", "36869")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 23, "page projection sequence not 23 frames")
    frame = frames[17]
    require(frame.get("uid") == "48064", "Page HT frame 17 changed")
    source_mux, target_mux = unique(root, "nMux", "48101"), unique(root, "nMux", "48263")
    require(source_mux in frame.iter() and target_mux in frame.iter(), "source/target mux not in frame 17")
    for uid, param in (("48083", "29"), ("48226", "168"), ("48677", "168")):
        ref = unique(root, "gRef", uid)
        require(ref in frame.iter(), f"reference {uid} is outside HT projection frame")
        require(ref.findtext("termList/*/dco/paramIdx") == param, f"reference {uid} param changed")
    signal_peers = [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in frame.findall("signalList/*")
    ]
    source_names = cluster_fields(main, "C4_IN_DIO96")
    target_names = cluster_fields(main, "Page HT")
    require(len(source_names) == 64 and len(target_names) == 28, "source/target schema size changed")
    results = []
    for source_idx, source_term, target_idx, target_term in WIRES:
        require(field_index(source_mux, source_term) == source_idx,
                f"source field index changed for {source_term}")
        require(field_index(target_mux, target_term) == target_idx,
                f"target field index changed for {target_term}")
        require(any({source_term, target_term} <= peers for peers in signal_peers),
                f"direct wire {source_term}->{target_term} absent")
        require(target_names[target_idx] == EXPECTED_NAMES[target_idx],
                f"Page HT label changed at {target_idx}")
        results.append(f"C4_IN[{source_idx}] {source_names[source_idx]} -> Page HT[{target_idx}] {target_names[target_idx]}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("main_xml", type=Path, nargs="?")
    args = parser.parse_args()
    for line in validate(args.source, args.main_xml):
        print(line)
    print("PASS: seven non-inverted C4 input -> Page HT display wires")


if __name__ == "__main__":
    main()
