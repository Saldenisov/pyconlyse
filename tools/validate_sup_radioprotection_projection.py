"""Read-only wire check of Supervision radioprotection display and graph input.

Usage: python tools/validate_sup_radioprotection_projection.py SOURCE_EXPORT_ZIP
       python tools/validate_sup_radioprotection_projection.py BDHB_XML MAIN_XML
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

# Destination Page Radioprotection index, C4 input index, source terminal,
# target terminal. Every pair is a direct signal in diagram 2928.
WIRES = (
    (0, 53, "30009", "43777"),
    (1, 52, "58933", "56271"),
    (2, 54, "58938", "56276"),
    (3, 55, "58941", "56279"),
    (4, 60, "60933", "29160"),
    (5, 63, "53398", "53920"),
    (6, 62, "61425", "29201"),
    (7, 61, "61420", "29190"),
    (8, 57, "798", "56285"),
    (9, 58, "60927", "56289"),
    (10, 59, "60930", "56802"),
    (11, 56, "58944", "56282"),
)
EXPECTED_TARGET_NAMES = (
    "Porte lourde",
    "Porte légére",
    "Porte de Secours",
    "Porte Laser",
    "Rondiers",
    "Occulteur LASER",
    "BACO-TIR EN/HORS",
    "BACO PA/MOD",
    "RONDIER 1",
    "RONDIER 2",
    "RONDIER 3",
    "ARRETS D'URGENCE",
)

# Page field index, page-unbundle terminal, compound-AND input terminal,
# inverted at that input. Fields 5 and 8-10 do not enter this aggregate.
SUMMARY_WIRES = (
    (0, "4173", "4305", False),
    (1, "4206", "4314", False),
    (2, "4236", "5890", False),
    (3, "4245", "5908", False),
    (4, "4254", "5919", True),
    (11, "4263", "15936", False),
    (6, "4272", "15951", True),
    (7, "51066", "29335", False),
)


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


def cluster_fields(main: ET.Element, label: str) -> list[str]:
    section = main.find("VCTP/Section")
    require(section is not None, "VCTP/Section absent")
    flat = [item for item in section if item.tag == "TypeDesc" and item.get("Type")]
    matches = [item for item in flat if item.get("Type") == "Cluster" and item.get("Label") == label]
    require(len(matches) == 1, f"expected one {label} type")
    return [flat[int(child.get("TypeID", "-1"))].get("Label", "") for child in matches[0]]


def field_index(mux: ET.Element, term_uid: str) -> int:
    matches = [term for term in mux.findall("termList/*") if term.get("uid") == term_uid]
    require(len(matches) == 1, f"terminal {term_uid} absent from mux {mux.get('uid')}")
    return int(matches[0].findtext("dco/i", default="0"))


def direct(peers: list[set[str]], source: str, target: str) -> None:
    require(any({source, target} <= pair for pair in peers),
            f"direct wire {source}->{target} absent")


def validate(source_path: Path, main_path: Path | None = None) -> list[str]:
    if main_path is None:
        root, main = checked_export_archive(source_path)
    else:
        root = checked_root(source_path, BDHB_SHA256)
        main = checked_root(main_path, MAIN_SHA256)
    sequence = unique(root, "sequence", "36869")
    frames = sequence.find("diagramList")
    require(frames is not None and len(frames) == 23, "projection sequence not 23 frames")
    frame = frames[16]
    require(frame.get("uid") == "2928", "radioprotection frame 16 changed")
    nodes = frame.find("nodeList")
    require(nodes is not None, "frame node list absent")
    require({node.get("uid") for node in nodes} ==
            {"2986", "29714", "29989", "42797", "43587", "43860"},
            "frame node set changed")
    source_mux = unique(root, "nMux", "29989")
    target_mux = unique(root, "nMux", "43587")
    for uid, param in (("29714", "29"), ("42797", "2"), ("43860", "2")):
        ref = unique(root, "gRef", uid)
        require(ref.findtext("termList/*/dco/paramIdx") == param,
                f"reference {uid} parameter changed")
    peers = [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in frame.findall("signalList/*")
    ]
    for source_term, target_term in (
        ("29724", "29997"),  # C4 bank to source unbundle
        ("43295", "43775"),  # old display cluster to target bundle
        ("43750", "43865"),  # updated display cluster to local
    ):
        direct(peers, source_term, target_term)
    source_names = cluster_fields(main, "C4_IN_DIO96")
    target_names = cluster_fields(main, "Page Radioprotection")
    require(len(source_names) == 64 and len(target_names) == 12,
            "source/target schema size changed")
    require(tuple(target_names) == EXPECTED_TARGET_NAMES,
            "Page Radioprotection labels changed")
    results = []
    for target_idx, source_idx, source_term, target_term in WIRES:
        require(field_index(source_mux, source_term) == source_idx,
                f"source index changed for terminal {source_term}")
        require(field_index(target_mux, target_term) == target_idx,
                f"target index changed for terminal {target_term}")
        direct(peers, source_term, target_term)
        results.append(
            f"C4_IN[{source_idx}] {source_names[source_idx]} -> "
            f"Page Radioprotection[{target_idx}] {target_names[target_idx]}"
        )

    summary_sequence = unique(root, "sequence", "49452")
    summary_frames = summary_sequence.find("diagramList")
    require(summary_frames is not None and len(summary_frames) == 12,
            "graph-summary sequence not 12 frames")
    summary_frame = summary_frames[5]
    require(summary_frame.get("uid") == "4090", "graph-summary frame 5 changed")
    summary_nodes = summary_frame.find("nodeList")
    require(summary_nodes is not None and
            {node.get("uid") for node in summary_nodes} ==
            {"4102", "4123", "4153", "4284", "29466"},
            "graph-summary node set changed")
    for uid, param in (("4123", "2"), ("29466", "58")):
        require(unique(root, "gRef", uid).findtext("termList/*/dco/paramIdx") == param,
                f"summary reference {uid} parameter changed")
    summary_mux = unique(root, "nMux", "4153")
    arithmetic = unique(root, "cpdArith", "4284")
    flags = int(arithmetic.findtext("objFlags", default="0"))
    require((flags >> 16) & 7 == 2, "aggregate is no longer compound AND")
    summary_peers = [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in summary_frame.findall("signalList/*")
    ]
    direct(summary_peers, "4135", "4159")  # Page cluster to unbundle
    direct(summary_peers, "4296", "29495")  # AND result to local paramIdx 58
    for page_idx, page_term, input_term, inverted in SUMMARY_WIRES:
        require(field_index(summary_mux, page_term) == page_idx,
                f"summary Page field index changed at {page_term}")
        inputs = [term for term in arithmetic.findall("termList/*")
                  if term.get("uid") == input_term]
        require(len(inputs) == 1, f"aggregate input terminal {input_term} absent")
        input_flags = int(inputs[0].findtext("dco/objFlags", default="0"))
        require(bool(input_flags & 0x10000) == inverted,
                f"input inversion changed at {input_term}")
        direct(summary_peers, page_term, input_term)
    require({ref.get("uid") for ref in root.findall(".//*[@class='gRef']")
             if ref.findtext("termList/*/dco/paramIdx") == "58"} ==
            {"29466", "60996"}, "summary-local consumers changed")
    consumer = unique(root, "diag", "37185")
    graph = unique(root, "iUse", "46000")
    require(graph in consumer.iter(), "graph subVI not in consumer frame")
    require('"2_SUP_Graph _Radioprot.vi"' in
            [part.text for part in graph.iter("text")], "graph subVI identity changed")
    graph_inputs = [term for term in graph.findall("termList/*")
                    if term.get("uid") == "62003"]
    require(len(graph_inputs) == 1 and
            graph_inputs[0].findtext("dco/paramIdx") == "9",
            "graph connector 9 changed")
    consumer_peers = [
        {term.get("uid", "") for term in signal.findall("termList/*")}
        for signal in consumer.findall("signalList/*")
    ]
    direct(consumer_peers, "61003", "62003")
    results.append(
        "graph input: Page fields 0,1,2,3,11,7 AND NOT 4,6; "
        "local paramIdx 58 -> 2_SUP_Graph _Radioprot.vi connector 9"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("main_xml", type=Path, nargs="?")
    args = parser.parse_args()
    for line in validate(args.source, args.main_xml):
        print(line)
    print("PASS: 12 display wires and eight-input graph aggregate")


if __name__ == "__main__":
    main()
