"""Inventory direct DIO-output or DPS/EPS status field assignments from raw VI XML.

The local ``paramIdx`` identities were established from direct PSP
URI wires, not inferred from front-panel ordering. A row is emitted only
when a bundle-by-name output connects to the write-side local reference.
Unwired and whole-cluster assignments are outside this ledger. Read-only.
"""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


BANK_GROUPS = {
    "dio": {13: "C5_OUT_DIO96", 15: "C4_OUT_DIO96", 17: "C3_OUT_DIO96"},
    "status": {36: "DPS", 37: "DPC", 38: "EPC", 44: "EPS"},
}
TYPE_ID_RE = re.compile(r"TypeID\((\d+)\)")


def scope_path(node: ET.Element, parents: dict[ET.Element, ET.Element]) -> str:
    scopes = []
    current = node
    child_diag: ET.Element | None = None
    scope_classes = {"sequence", "select", "event", "eventStruct", "whileLoop", "forLoop", "diagramDisable"}
    while current in parents:
        current = parents[current]
        if current.get("class") == "diag":
            child_diag = current
        if current.get("class") not in scope_classes:
            continue
        idx = "?"
        diagrams = current.find("diagramList")
        if child_diag is not None and diagrams is not None:
            for i, diagram in enumerate(diagrams):
                if diagram.get("uid") == child_diag.get("uid"):
                    idx = str(i)
                    break
        scopes.append(f"{current.get('class')}:{current.get('uid')}[{idx}]")
        child_diag = None
    return "/".join(reversed(scopes))


def control_label(control: ET.Element) -> str:
    parts = control.find("ddo/partsList")
    if parts is None:
        return ""
    for part in parts:
        if part.get("class") == "label" and part.findtext("partID") == "16":
            return (part.findtext("textRec/text") or "").strip('"')
    return ""


def field_labels(main_xml: Path, fp_xml: Path, banks: dict[int, str]) -> dict[str, list[str]]:
    main_text = main_xml.read_text(encoding="utf-8")
    heap_to_consolidated = {
        int(heap): int(consolidated)
        for heap, consolidated in re.findall(r"Heap TypeID\s+(\d+)\s+= Consolidated TypeID\s+(\d+):", main_text)
    }
    main = ET.fromstring(main_text)
    vctp = main.find("VCTP/Section")
    if vctp is None:
        raise RuntimeError("VCTP section missing")
    flat_defs = [element for element in vctp if element.tag == "TypeDesc" and element.get("Type")]
    consolidated_to_flat = {
        int(element.get("Index", "-1")): int(element.get("FlatTypeID", "-1"))
        for element in vctp.iter("TypeDesc")
        if element.get("Index") is not None and element.get("FlatTypeID") is not None
    }
    fp = ET.parse(fp_xml).getroot()
    result = {}
    for control in fp.findall(".//*[@class='fPDCO']"):
        name = control_label(control)
        if name not in banks.values():
            continue
        type_desc = control.findtext("typeDesc", default="")
        match = TYPE_ID_RE.fullmatch(type_desc)
        if not match:
            raise RuntimeError(f"No type ID for {name}")
        consolidated = heap_to_consolidated[int(match.group(1))]
        flat_idx = consolidated_to_flat[consolidated]
        cluster = flat_defs[flat_idx]
        if cluster.get("Type") != "Cluster":
            raise RuntimeError(f"Expected cluster type for {name}")
        result[name] = [flat_defs[int(child.get("TypeID", "-1"))].get("Label", "") for child in cluster]
    if set(result) != set(banks.values()):
        raise RuntimeError(f"Missing output-bank field descriptors: {set(banks.values()) - set(result)}")
    return result


def bool_value(raw: str | None) -> str:
    if raw == "0000":
        return "False"
    if raw == "01":
        return "True"
    return "" if raw is None else f"raw:{raw}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdhb_xml", type=Path)
    parser.add_argument("fphb_xml", type=Path)
    parser.add_argument("main_xml", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--bank-group", choices=sorted(BANK_GROUPS), default="dio")
    args = parser.parse_args()
    banks = BANK_GROUPS[args.bank_group]
    labels = field_labels(args.main_xml, args.fphb_xml, banks)
    root = ET.parse(args.bdhb_xml).getroot()
    parents = {child: parent for parent in root.iter() for child in parent}
    term_owner: dict[str, ET.Element] = {}
    term_element: dict[str, ET.Element] = {}
    for node in root.iter():
        if not node.get("class") or node.get("class") == "signal":
            continue
        term_list = node.find("termList")
        for term in term_list if term_list is not None else []:
            if term.get("class") == "term" and term.get("uid"):
                term_owner[term.get("uid", "")] = node
                term_element[term.get("uid", "")] = term
    links: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for signal in root.findall(".//*[@class='signal']"):
        term_list = signal.find("termList")
        if term_list is None:
            continue
        terms = [term.get("uid", "") for term in term_list]
        for term in terms:
            for other in terms:
                if other != term:
                    links[term].append((signal.get("uid", ""), other))

    rows = []
    for gref in root.findall(".//*[@class='gRef']"):
        own_term = gref.find("termList/*")
        if own_term is None:
            continue
        idx = own_term.findtext("dco/paramIdx")
        if not idx or not idx.isdigit() or int(idx) not in banks:
            continue
        if not int(own_term.findtext("objFlags", default="0")) & 0x8000:
            continue  # read-side local, not a write-side assignment
        bank = banks[int(idx)]
        own_uid = own_term.get("uid", "")
        for _signal, peer_uid in links.get(own_uid, []):
            mux = term_owner.get(peer_uid)
            if mux is None or mux.get("class") != "nMux" or mux.findtext("objFlags") != "262144":
                continue
            mux_terms = mux.find("termList")
            for field_term in mux_terms if mux_terms is not None else []:
                if field_term.get("uid") == peer_uid:
                    continue
                flags = int(field_term.findtext("objFlags", default="0"))
                if not flags & 0x8000 or flags & 0x20000:
                    continue  # skip whole-cluster input; keep selected field inputs
                field_idx = int(field_term.findtext("dco/i", default="0"))
                if field_idx >= len(labels[bank]):
                    raise RuntimeError(f"{bank} field index {field_idx} out of range")
                for signal_uid, source_term_uid in links.get(field_term.get("uid", ""), []):
                    source_node = term_owner.get(source_term_uid)
                    source_term = term_element.get(source_term_uid)
                    if source_node is None or source_term is None:
                        continue
                    if source_node is mux:
                        continue  # sibling bundle inputs can share one fanned-out source wire
                    const_hex = source_term.findtext("dco/ConstValue") if source_node.get("class") == "sRN" else None
                    rows.append({
                        "bank": bank,
                        "param_idx": idx,
                        "field_idx": field_idx,
                        "field_label": labels[bank][field_idx],
                        "literal_value": bool_value(const_hex) if const_hex is not None else "",
                        "source_class": source_node.get("class", ""),
                        "source_uid": source_node.get("uid", ""),
                        "source_term_uid": source_term_uid,
                        "field_signal_uid": signal_uid,
                        "gref_uid": gref.get("uid", ""),
                        "mux_uid": mux.get("uid", ""),
                        "scope_path": scope_path(gref, parents),
                    })
    wire_keys = {
        (row["bank"], row["gref_uid"], row["mux_uid"], row["field_idx"], row["field_signal_uid"])
        for row in rows
    }
    if len(wire_keys) != len(rows):
        raise RuntimeError("A field wire has multiple candidate sources; do not count it twice")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as stream:
        fields = ["bank", "param_idx", "field_idx", "field_label", "literal_value", "source_class", "source_uid", "source_term_uid", "field_signal_uid", "gref_uid", "mux_uid", "scope_path"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"field-assignment wire rows: {len(rows)}")
    for bank in banks.values():
        subset = [row for row in rows if row["bank"] == bank]
        print(f"{bank}: {len(subset)} assignments, {sum(bool(row['literal_value']) for row in subset)} literal values, {len({row['field_idx'] for row in subset})} distinct fields")
    if args.bank_group == "dio":
        for bank, idx in (("C4_OUT_DIO96", 18), ("C4_OUT_DIO96", 19), ("C4_OUT_DIO96", 20), ("C3_OUT_DIO96", 1), ("C3_OUT_DIO96", 4)):
            print(f"type check {bank}[{idx}]: {labels[bank][idx]}")


if __name__ == "__main__":
    main()
