"""Decode startup AO/DO literals into seven target-bank vectors from ACQ XML.

Read-only. These are LabVIEW logical command values, not measured output volts
or independently verified physical line states.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


START_NODE_UID = "14814"
BANKS = ("C6NI6703", "C7NI6703", "C8NI6703", "C9NI6703", "C3_OUT_DIO96", "C4_OUT_DIO96", "C5_OUT_DIO96")
PARAM_TO_BANK = {9: "C6NI6703", 10: "C7NI6703", 11: "C8NI6703", 12: "C9NI6703", 17: "C3_OUT_DIO96", 15: "C4_OUT_DIO96", 13: "C5_OUT_DIO96"}


def bank_types(main_path: Path, fp_path: Path) -> dict[str, list[tuple[str, str]]]:
    main_text = main_path.read_text(encoding="utf-8")
    heap_to_consolidated = {
        int(heap): int(consolidated)
        for heap, consolidated in re.findall(r"Heap TypeID\s+(\d+)\s+= Consolidated TypeID\s+(\d+):", main_text)
    }
    root = ET.fromstring(main_text)
    section = root.find("VCTP/Section")
    if section is None:
        raise RuntimeError("VCTP/Section absent")
    flat = [node for node in section if node.tag == "TypeDesc" and node.get("Type")]
    consolidated_to_flat = {
        int(node.get("Index", "-1")): int(node.get("FlatTypeID", "-1"))
        for node in section.iter("TypeDesc")
        if node.get("Index") is not None and node.get("FlatTypeID") is not None
    }
    fp = ET.parse(fp_path).getroot()
    control_type = {}
    for control in fp.findall(".//*[@class='fPDCO']"):
        for part in control.findall("ddo/partsList/*"):
            if part.get("class") != "label" or part.findtext("partID") != "16":
                continue
            name = (part.findtext("textRec/text") or "").strip('"')
            if name in BANKS:
                match = re.fullmatch(r"TypeID\((\d+)\)", control.findtext("typeDesc", default=""))
                if match is None:
                    raise RuntimeError(f"Missing front-panel type for {name}")
                control_type[name] = int(match.group(1))
    result = {}
    for bank in BANKS:
        cluster = flat[consolidated_to_flat[heap_to_consolidated[control_type[bank]]]]
        if cluster.get("Type") != "Cluster":
            raise RuntimeError(f"Startup {bank} constant does not have cluster type")
        if cluster.get("Label") != bank:
            raise RuntimeError(f"Front-panel type for {bank} is {cluster.get('Label')}")
        result[bank] = [
            (flat[int(item.get("TypeID", "-1"))].get("Type", ""), flat[int(item.get("TypeID", "-1"))].get("Label", ""))
            for item in cluster
        ]
    return result


def constant_label(dco: ET.Element) -> str:
    for part in dco.findall("ddo/partsList/*"):
        if part.get("class") == "label" and part.findtext("partID") == "16":
            return (part.findtext("textRec/text") or "").strip('"')
    return ""


def constants(bdhb_path: Path) -> dict[str, tuple[bytes, int, str, str, str]]:
    root = ET.parse(bdhb_path).getroot()
    node = root.find(f".//*[@class='sRN'][@uid='{START_NODE_UID}']")
    if node is None:
        raise RuntimeError(f"Startup constant node {START_NODE_UID} absent")
    diagram = root.find(".//*[@class='diag'][@uid='14803']")
    if diagram is None:
        raise RuntimeError("Startup assignment diagram 14803 absent")
    gref_by_term = {}
    for gref in diagram.findall("zPlaneList/*"):
        if gref.get("class") != "gRef":
            continue
        for term in gref.findall("termList/*"):
            idx = term.findtext("dco/paramIdx", default="")
            if idx.isdigit() and int(idx) in PARAM_TO_BANK:
                gref_by_term[term.get("uid", "")] = (int(idx), gref.get("uid", ""))
    targets_by_source = {}
    for signal in diagram.findall("signalList/*"):
        signal_terms = {term.get("uid", "") for term in signal.findall("termList/*")}
        source_terms = {term.get("uid", "") for term in node.findall("termList/*")}
        for source_uid in signal_terms & source_terms:
            targets = [gref_by_term[uid] for uid in signal_terms if uid in gref_by_term]
            if not targets:
                raise RuntimeError(f"Startup source term {source_uid}: no mapped local")
            targets_by_source[source_uid] = targets
    result = {}
    for term in node.findall("termList/*"):
        dco = term.find("dco")
        if dco is None or dco.get("class") != "bDConstDCO":
            continue
        term_uid = term.get("uid", "")
        if term_uid not in targets_by_source:
            raise RuntimeError(f"Startup constant term {term_uid} has no mapped bank local")
        caption = constant_label(dco)
        raw = dco.findtext("ConstValue")
        type_match = re.fullmatch(r"TypeID\((\d+)\)", dco.findtext("typeDesc", default=""))
        if raw is None or type_match is None:
            raise RuntimeError(f"Missing startup constant value/type for term {term_uid}")
        for param_idx, gref_uid in targets_by_source[term_uid]:
            bank = PARAM_TO_BANK[param_idx]
            if bank in result:
                raise RuntimeError(f"Duplicate startup bank {bank}")
            result[bank] = (bytes.fromhex(raw), int(type_match.group(1)), caption, term_uid, gref_uid)
    if set(result) != set(BANKS):
        raise RuntimeError(f"Startup bank mismatch: {set(result) ^ set(BANKS)}")
    return result


def decode(bdhb_path: Path, fp_path: Path, main_path: Path) -> list[dict[str, str | int]]:
    sources = constants(bdhb_path)
    schemas = bank_types(main_path, fp_path)
    rows = []
    for bank in BANKS:
        fields = schemas[bank]
        blob = sources[bank][0]
        kind = "AO" if "NI6703" in bank else "DO"
        expected_type = "NumFloat64" if kind == "AO" else "Boolean"
        if any(type_name != expected_type for type_name, _ in fields):
            raise RuntimeError(f"Non-{expected_type} field in {bank}")
        width = 8 if kind == "AO" else 1
        expected_bytes = len(fields) * width
        if len(blob) == expected_bytes + 1 and blob[-1] == 0:
            blob = blob[:-1]  # saved cluster constant contains one zero pad byte
        if len(blob) != expected_bytes:
            raise RuntimeError(f"{bank}: {len(blob)} bytes for {len(fields)} fields")
        for index, (_, label) in enumerate(fields):
            field_blob = blob[index * width:(index + 1) * width]
            if kind == "AO":
                value = repr(struct.unpack(">d", field_blob)[0])
            else:
                if field_blob[0] not in (0, 1):
                    raise RuntimeError(f"Unexpected Boolean encoding {field_blob.hex()} for {bank}[{index}]")
                value = "True" if field_blob[0] else "False"
            rows.append({
                "bank": bank,
                "kind": kind,
                "field_idx": index,
                "field_label": label,
                "logical_value": value,
                "raw_hex": field_blob.hex().upper(),
                "source_node_uid": START_NODE_UID,
                "source_term_uid": sources[bank][3],
                "target_gref_uid": sources[bank][4],
                "literal_caption": sources[bank][2],
                "literal_type_heap": sources[bank][1],
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("fphb_xml", type=Path)
    parser.add_argument("main_xml", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args()
    rows = decode(args.bdhb_xml, args.fphb_xml, args.main_xml)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Decoded {len(rows)} startup logical values -> {args.output_csv}")
    for bank in BANKS:
        selected = [row for row in rows if row["bank"] == bank and row["logical_value"] not in ("False", "0.0")]
        print(f"{bank}: {len(selected)} nonzero/True of {sum(row['bank'] == bank for row in rows)}")
        for row in selected:
            print(f"  [{row['field_idx']}] {row['logical_value']}: {row['field_label']}")


if __name__ == "__main__":
    main()
