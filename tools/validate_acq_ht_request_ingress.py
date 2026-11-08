"""Verify saved Acquisition DPS[15] -> HT-start event wires, offline only.

Usage: python tools/validate_acq_ht_request_ingress.py SOURCE_EXPORT_ZIP
No VI, PSP variable, or NI card is accessed.
"""

from __future__ import annotations

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ARCHIVE_SHA256 = "6A518B319B2D35B465DB9AAB557CCA751ACC8B58A600FBA0B8E13771B6EA1527"
BDHB_SHA256 = "36E2857BF3031A1C7AB5A5BE9C8A0C2FADEB91E32D60A29652F536F7F3DDB5CB"
MAIN_SHA256 = "71E0929301A628DB3DB814C1ADF8C679C6AEF1C10416BFAFD139EED636C59AAC"


def require(condition: bool, reason: str) -> None:
    if not condition:
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
            "block diagram export hash changed")
    require(hashlib.sha256(types).hexdigest().upper() == MAIN_SHA256,
            "main VI export hash changed")
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


def reference_indexes(diagram: ET.Element) -> set[str]:
    return {ref.findtext("termList/*/dco/paramIdx")
            for ref in diagram.iter() if ref.get("class") == "gRef"}


def cluster_fields(main: ET.Element, label: str) -> list[str]:
    section = main.find("VCTP/Section")
    require(section is not None, "VCTP type section absent")
    flat = [item for item in section if item.tag == "TypeDesc" and item.get("Type")]
    matches = [item for item in flat if item.get("Type") == "Cluster" and item.get("Label") == label]
    require(len(matches) == 1, f"expected one {label} cluster")
    return [flat[int(item.get("TypeID", "-1"))].get("Label", "") for item in matches[0]]


def validate(path: Path) -> None:
    root, main = checked_archive(path)
    dps_fields = cluster_fields(main, "DPS")
    require(len(dps_fields) == 29 and dps_fields[15] == "X Marche alimentation HT",
            "DPS HT-start field order changed")
    runtime = unique(root, "eventStruct", "43")
    runtime_frames = runtime.find("diagramList")
    require(runtime_frames is not None and len(runtime_frames) == 26,
            "ACQ runtime event frame count changed")
    timeout = runtime_frames[0]
    require(timeout.get("uid") == "53", "timeout case changed")
    sequence = unique(root, "sequence", "10111")
    require(sequence in timeout.iter(), "four-frame timeout sequence moved")
    frames = sequence.find("diagramList")
    require(frames is not None and [x.get("uid") for x in frames] ==
            ["10115", "10526", "22247", "42045"],
            "timeout sequence frames changed")
    read_frame, dispatch_frame = frames[0], frames[2]
    read = unique(root, "sharedVariableDynamicRead", "19950")
    require(read in read_frame.iter(), "DPS timeout read moved")
    for uid in ("87", "19926"):
        ref = unique(root, "gRef", uid)
        require(ref in read_frame.iter()
                and ref.findtext("termList/*/dco/paramIdx") == "36",
                f"DPS read-side local {uid} changed")
    read_peers = peers(read_frame)
    wire(read_peers, "19968", "1819")
    wire(read_peers, "19929", "19965")

    require(reference_indexes(dispatch_frame) == {"21", "35", "36", "39", "43"},
            "timeout dispatch local-reference set changed")
    dps = unique(root, "gRef", "1823")
    require(dps in dispatch_frame.iter()
            and dps.findtext("termList/*/dco/paramIdx") == "36",
            "dispatcher source no longer DPS local")
    dispatch_peers = peers(dispatch_frame)
    for source, target in (
        ("15714", "21322"),  # DPS cluster -> Boolean array
        ("21306", "22224"),  # array -> Search 1D Array
        ("11758", "22221"),  # True search element
        ("22214", "17625"),  # first-True index -> Increment
        ("17622", "15005"),  # one-based selector -> case 8105
    ):
        wire(dispatch_peers, source, target)
    for uid, primitive_id in (("21295", "1169"), ("22203", "1901"),
                              ("17616", "1057")):
        node = unique(root, "prim", uid)
        require(node in dispatch_frame.iter()
                and node.findtext("primResID") == primitive_id,
                f"dispatcher primitive {uid} changed")
    # The source terminal is a node-list Boolean constant; its data-fill is 01.
    true_terms = [term for term in dispatch_frame.findall("nodeList/*/termList/*")
                  if term.get("uid") == "11758"]
    require(len(true_terms) == 1
            and true_terms[0].findtext("dco/ConstValue") == "01",
            "Search 1D Array element is no longer literal True")
    dispatcher = unique(root, "select", "8105")
    require(dispatcher in dispatch_frame.iter(), "DPS selector moved")
    case_ranges = dispatcher.find("SelectRangeArray32")
    require(case_ranges is not None and len(case_ranges) == 25
            and [(int(case.findtext("start", "-1")),
                  int(case.findtext("diagramIdx", "-1")))
                 for case in case_ranges] == [(index, index) for index in range(25)],
            "DPS selector case range changed")
    request_arm = dispatcher.find("diagramList")[16]
    require(request_arm.get("uid") == "17382", "DPS[15] arm changed")
    property_node = unique(root, "propNode", "22889")
    require(property_node in request_arm.iter()
            and property_node.find("ddo").get("uid") == "59314",
            "HT start property target changed")
    require([item.text.strip('"') for item in property_node.findall(
        "termList/*/dco/propList/*/PropItemName"
    )] == ["Value", "Val(Sgnl)"], "HT start property names changed")
    wire(peers(request_arm), "23094", "23027")
    wire(peers(request_arm), "23094", "23071")
    true_terms = [term for term in request_arm.findall("nodeList/*/termList/*")
                  if term.get("uid") == "23094"]
    require(len(true_terms) == 1
            and true_terms[0].findtext("dco/ConstValue") == "01",
            "HT start property value no longer literal True")
    registered = [entry for entry in runtime.find("EventNodeEvents")
                  if entry.findtext("diagramIdx") == "20"]
    require(len(registered) == 1
            and registered[0].findtext("ddoUID") == "59314",
            "HT-start property target not registered to event 20")

    ht_event = runtime_frames[20]
    require(ht_event.get("uid") == "48846", "HT-start event frame changed")
    event_peers = peers(ht_event)
    event_data = unique(root, "eventDataNode", "48862")
    require(event_data in ht_event.iter(), "HT-start event-data node moved")
    new_value = [term for term in event_data.findall("termList/*")
                 if term.get("uid") == "53951"]
    require(len(new_value) == 1 and new_value[0].findtext("dco/i") == "6",
            "HT-start event Boolean value terminal changed")
    wire(event_peers, "53951", "53960")
    event_branch = unique(root, "select", "53958")
    require(event_branch in ht_event.iter(), "HT-start NewVal case moved")
    event_cases = event_branch.find("SelectRangeArray32")
    require(event_cases is not None and [
        (case.findtext("start"), case.findtext("diagramIdx"))
        for case in event_cases
    ] == [("0", "0"), ("1", "1")], "HT-start NewVal case order changed")
    false_arm, true_arm = event_branch.find("diagramList")
    require(false_arm.get("uid") == "53972"
            and len(false_arm.find("zPlaneList")) == 0,
            "HT-start NewVal=False arm no longer empty")
    require(true_arm.get("uid") == "53978"
            and unique(root, "sequence", "53984") in true_arm.iter(),
            "HT-start True procedure sequence moved")
    require(reference_indexes(ht_event) == {"15", "35", "36", "44"},
            "HT-start local-reference set changed")
    require("16" not in reference_indexes(dispatch_frame)
            and "16" not in reference_indexes(ht_event),
            "C4 input reference appeared in traced dispatch/event path")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_export_zip", type=Path)
    args = parser.parse_args()
    validate(args.source_export_zip)
    print("PASS: DPS[15] -> first-True selector 16 -> Val(Sgnl) -> HT event 20 True arm")
    print("PASS: no direct C4 input local reference in traced dispatch or event 20")


if __name__ == "__main__":
    main()
